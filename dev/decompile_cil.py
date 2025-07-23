#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
import shutil
from argparse import ArgumentParser
from functools import partial
from itertools import chain
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from sepolicy.cil_rule import CilRule
from sepolicy.classmap import Classmap
from sepolicy.conditional_type import ConditionalType
from sepolicy.config import default_variables, default_variables_choices
from sepolicy.macro import (
    categorize_macros,
    decompile_ioctl_defines,
    decompile_ioctls,
    decompile_macros,
    decompile_perms,
    expand_macro_bodies,
    macro_conditionals,
    macro_name,
    read_macros,
    resolve_macro_paths,
    split_macros_text_name_body,
)
from sepolicy.match import (
    RuleMatch,
    match_macro_rules,
    merge_class_sets,
    merge_ioctl_rules,
    merge_typeattribute_rules,
    replace_ioctls,
    replace_macro_rules,
    replace_perms,
)
from sepolicy.match_extract import rule_extract_part_iter
from sepolicy.output import (
    group_rules,
    output_contexts,
    output_genfs_contexts,
    output_grouped_rules,
)
from sepolicy.rule import RULE_DYNAMIC_PARTS_INDEX, Rule
from utils.mld import MultiLevelDict
from utils.utils import Color, android_root, color_print


def get_macros_path(version: Optional[str], current: bool):
    system_sepolicy = Path(android_root, 'system/sepolicy')
    if version is None or current:
        return system_sepolicy

    return Path(system_sepolicy, f'prebuilts/api/{version}')


def print_macro_file_paths(macro_file_paths: List[str]):
    for macro_path in macro_file_paths:
        print(f'Loading macros: {macro_path}')


def print_variable_ifelse(macros: List[str]):
    handled_variable_macro_ifelse = [
        'domain_trans',
    ]

    # Find conditional variables used in the input text
    # Conditional variables can be specified, but we need to know if the
    # macro arguments are used in them
    for macro in macros:
        name = macro_name(macro)
        if name in handled_variable_macro_ifelse:
            continue

        conditional_variables = macro_conditionals(macro)
        for conditional_variable in conditional_variables:
            if conditional_variable.startswith('$'):
                print(
                    f'Macro {name} contains variable ifelse: {conditional_variable}'
                )


def rule_arity(rule: Rule):
    macro_rule_args = rule_extract_part_iter(
        rule.parts,
        rule.parts,
    )
    assert macro_rule_args is not None
    return len(macro_rule_args)


def sort_macros(macros: List[Tuple[str, List[Rule]]]):
    # Inside the macro, prefer rules with higher arity to help
    # the arg matching algorithm
    for macro in macros:
        rules = macro[1]
        rules.sort(key=rule_arity, reverse=True)


def decompile_one_cil(
    cil_path: str,
    conditional_types_map: Dict[str, ConditionalType],
    missing_generated_types: Set[str],
    version: Optional[str],
):
    cil_data = Path(cil_path).read_text()
    cil_lines = cil_data.splitlines()

    genfs_rules: List[Rule] = []

    # Convert lines to rules
    fn = partial(
        CilRule.from_line,
        conditional_types_map=conditional_types_map,
        missing_generated_types=missing_generated_types,
        genfs_rules=genfs_rules,
        version=version,
    )
    rules = list(chain.from_iterable(map(fn, cil_lines)))

    return rules, genfs_rules


def get_sdk_value(build_prop_path: Path):
    SDK_PROP = 'ro.build.version.sdk='
    sdk_value_str: Optional[str] = None

    for line in build_prop_path.read_text().splitlines():
        if line.startswith(SDK_PROP):
            sdk_value_str = line[len(SDK_PROP):]

    if sdk_value_str is None:
        return None

    # TODO: find the proper value
    if sdk_value_str == '36':
        return '202504'
    elif sdk_value_str == '35':
        return '202404'

    return sdk_value_str


def get_selinux_dir_policy(selinux_dir: str):
    partition_root = Path(selinux_dir).parent.parent
    dump_root = partition_root.parent

    partition_name = partition_root.name
    if partition_name == 'vendor':
        platform_policy_path = Path(selinux_dir, 'plat_pub_versioned.cil')
        assert platform_policy_path.exists(), platform_policy_path

        policy_version_path = Path(selinux_dir, 'plat_sepolicy_vers.txt')
        assert policy_version_path.exists(), policy_version_path

        policy_version = policy_version_path.read_text().strip()
    else:
        platform_policy_path = Path(
            dump_root,
            'system/etc/selinux/plat_sepolicy.cil',
        )
        assert platform_policy_path.exists(), platform_policy_path

        platform_build_prop_path = Path(dump_root, 'system/build.prop')
        policy_version = get_sdk_value(platform_build_prop_path)

    policy_path = Path(selinux_dir, f'{partition_name}_sepolicy.cil')
    assert policy_path.exists(), policy_path

    return str(platform_policy_path), str(policy_path), policy_version


def decompile_cil():
    parser = ArgumentParser(
        prog='decompile_cil.py',
        description='Decompile CIL files',
    )
    parser.add_argument(
        '--version',
        action='store',
        help='Version string (eg: 31)',
    )
    parser.add_argument(
        '--current',
        action='store_true',
        help='Use current macros (rather than versioned macros)',
    )
    parser.add_argument(
        '--platform',
        action='store',
        help='Path to platform policy (eg: vendor/etc/selinux/plat_pub_versioned.cil)',
    )
    parser.add_argument(
        '--policy',
        action='store',
        help='Path to policy (eg: vendor/etc/selinux/vendor_sepolicy.cil)',
    )
    parser.add_argument(
        '-s',
        '--selinux',
        action='store',
        help='Path to selinux directory (eg: vendor/etc/selinux)',
    )
    parser.add_argument(
        '-m',
        '--macros',
        action='store',
        help='Path to directory containing macros',
    )
    parser.add_argument(
        '--extra-macros',
        action='append',
        default=[],
        help='Path to files or directories containing extra macros',
    )
    parser.add_argument(
        '-v',
        '--var',
        action='append',
        default=[],
        help='Variable used when expanding macros',
    )
    parser.add_argument(
        '-o',
        '--output',
        action='store',
        required=True,
        help='Output directory for the decompiled selinux',
    )

    args = parser.parse_args()

    macros: Optional[str] = args.macros
    extra_macros: List[str] = args.extra_macros
    output_dir: str = args.output
    selinux_dir: Optional[str] = args.selinux

    if selinux_dir is None:
        platform_policy: Optional[str] = args.platform

        assert args.policy is not None
        policy: str = args.policy

        version: Optional[str] = args.version
    else:
        platform_policy, policy, version = get_selinux_dir_policy(selinux_dir)

    if not macros:
        macros = str(get_macros_path(version, args.current))

    print(f'Found platform policy: {platform_policy}')
    print(f'Found policy: {policy}')
    print(f'Found policy version: {version}')

    conditional_types_map: Dict[str, ConditionalType] = {}
    missing_generated_types: Set[str] = set()

    # Only load generated types from platform policy
    if platform_policy is not None:
        _, _ = decompile_one_cil(
            platform_policy,
            conditional_types_map,
            set(),
            version,
        )

    rules, genfs_rules = decompile_one_cil(
        policy,
        conditional_types_map,
        missing_generated_types,
        version,
    )

    mld: MultiLevelDict[Rule] = MultiLevelDict()
    for rule in rules:
        # Add partial matches to this rule
        # Start partial matching after the first key
        mld.add(rule.hash_values, rule, RULE_DYNAMIC_PARTS_INDEX)

    macro_file_paths, access_vectors_path = resolve_macro_paths([macros])
    extra_macro_file_paths, _ = resolve_macro_paths(extra_macros)
    macro_file_paths += extra_macro_file_paths

    print_macro_file_paths(macro_file_paths)
    print(f'Loading access vectors: {access_vectors_path}')

    input_text, macros_text = read_macros(macro_file_paths)

    print_variable_ifelse(macros_text)

    variables = default_variables.copy()
    variables_choices = default_variables_choices.copy()

    for kv in args.var:
        k, v = kv.split('=')
        variables[k] = v

        if k in variables_choices:
            del variables_choices[k]

    expanded_macros_text = expand_macro_bodies(
        input_text,
        macros_text,
        variables,
        variables_choices,
    )
    macros_name_body = split_macros_text_name_body(expanded_macros_text)

    expanded_macros, class_sets, perms, ioctls, ioctl_defines = (
        categorize_macros(macros_name_body)
    )
    decompiled_perms = decompile_perms(perms)
    decompiled_class_sets = decompile_perms(class_sets)
    decompiled_ioctls = decompile_ioctls(ioctls)
    decompiled_ioctl_defines = decompile_ioctl_defines(ioctl_defines)

    assert access_vectors_path is not None
    classmap = Classmap(access_vectors_path)

    macros_name_rules = decompile_macros(classmap, expanded_macros)

    sort_macros(macros_name_rules)

    color_print(f'Total rules: {len(mld)}', color=Color.GREEN)

    all_rule_matches: Set[RuleMatch] = set()
    for name, rules in macros_name_rules:
        match_macro_rules(
            mld,
            name,
            rules,
            all_rule_matches,
        )

    replace_macro_rules(mld, all_rule_matches)
    merge_typeattribute_rules(mld)
    merge_ioctl_rules(mld)

    replace_perms(mld, classmap, decompiled_perms)
    replace_ioctls(mld, decompiled_ioctls, decompiled_ioctl_defines)
    merge_class_sets(mld, decompiled_class_sets)

    # We can also merge target domains, but rules get long quickly
    # merge_target_domains(mld)

    color_print(f'Leftover rules: {len(mld)}', color=Color.GREEN)

    grouped_rules = group_rules(mld)

    shutil.rmtree(output_dir, ignore_errors=True)
    os.makedirs(output_dir)

    output_contexts(selinux_dir, output_dir)
    output_genfs_contexts(genfs_rules, output_dir)
    output_grouped_rules(grouped_rules, output_dir)


if __name__ == '__main__':
    decompile_cil()

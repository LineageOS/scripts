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
from sepolicy.config import default_variables
from sepolicy.macro import (
    categorize_macros,
    decompile_ioctl_defines,
    decompile_ioctls,
    decompile_macros,
    decompile_perms,
    expand_macro_bodies,
    macro_name_body_raw,
    macro_used_variables,
    read_macros,
    resolve_macro_paths,
)
from sepolicy.match import (
    RuleMatch,
    match_macro_rules,
    merge_class_sets,
    merge_ioctl_rules,
    merge_typeattribute_rules,
    remove_rules,
    remove_rules_from_rule_matches,
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
from sepolicy.rules import decompile_rules, resolve_rule_paths
from utils.mld import MultiLevelDict
from utils.utils import Color, android_root, color_print

system_sepolicy_path = Path(android_root, 'system/sepolicy')


def get_macros_path(version: Optional[str], current: bool):
    if version is None or current:
        return system_sepolicy_path

    return Path(system_sepolicy_path, f'prebuilts/api/{version}')


def print_macro_file_paths(macro_file_paths: List[str]):
    for macro_path in macro_file_paths:
        print(f'Loading macros: {macro_path}')


def print_rule_file_paths(rule_file_paths: List[str]):
    for rule_path in rule_file_paths:
        print(f'Loading rules: {rule_path}')


def gather_ifelse_variables(macros: List[str]):
    all_variables: Dict[str, Set[str]] = {}

    # Find conditional variables used in the input text
    # Conditional variables can be specified, but we need to know if the
    # macro arguments are used in them
    for macro in macros:
        name, body = macro_name_body_raw(macro)
        conditional_variables = macro_used_variables(name, body)
        all_variables.update(conditional_variables)

    return all_variables


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
            sdk_value_str = line[len(SDK_PROP) :]

    if sdk_value_str is None:
        return None

    # TODO: find the proper value
    if sdk_value_str == '36':
        return '202504'
    elif sdk_value_str == '35':
        return '202404'

    return f'{sdk_value_str}.0'


def get_selinux_dir_policy(selinux_dir: str):
    partition_root = Path(selinux_dir).parent.parent
    dump_root = partition_root.parent
    vendor_policy_path = Path(dump_root, 'vendor/etc/selinux')
    system_policy_path = Path(dump_root, 'system/etc/selinux')
    platform_build_prop_path = Path(dump_root, 'system/build.prop')

    partition_name = partition_root.name
    if partition_name in ['vendor', 'odm']:
        platform_policy_path = Path(
            vendor_policy_path,
            'plat_pub_versioned.cil',
        )
        assert platform_policy_path.exists(), platform_policy_path

        policy_version_path = Path(
            vendor_policy_path,
            'plat_sepolicy_vers.txt',
        )
        assert policy_version_path.exists(), policy_version_path

        policy_version = policy_version_path.read_text().strip()
    else:
        platform_policy_path = Path(
            system_policy_path,
            'plat_sepolicy.cil',
        )
        assert platform_policy_path.exists(), platform_policy_path

        policy_version = get_sdk_value(platform_build_prop_path)

    policy_path = Path(selinux_dir, f'{partition_name}_sepolicy.cil')

    if partition_name == 'system':
        policy_path = platform_policy_path
        platform_policy_path = None

    assert policy_path.exists(), policy_path

    return (
        str(platform_policy_path) if platform_policy_path is not None else None,
        str(policy_path),
        policy_version,
        partition_name,
    )


def decompile_cil():
    parser = ArgumentParser(
        prog='decompile_cil.py',
        description='Decompile CIL files',
    )
    parser.add_argument(
        '--version',
        action='store',
        help='Version string (eg: 31.0)',
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
        help='Path to directory containing macros '
        '(eg: system/sepolicy/prebuilts/api/31.0)',
    )
    parser.add_argument(
        '--extra-macros',
        action='append',
        default=[],
        help='Path to files or directories containing extra macros',
    )
    parser.add_argument(
        '-r',
        '--rules',
        action='append',
        help='Path to files or directories containing rules to be removed '
        '(eg: system/sepolicy/prebuilts/api/31.0), '
        'will default to the macros path if not specified',
    )
    parser.add_argument(
        '--extra-rules',
        action='append',
        default=[],
        help='Path to files or directories containing extra rules to be removed '
        '(eg: device/qcom/sepolicy_vndr/sm8450)',
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

    macro_paths: Optional[str] = args.macros
    rule_paths: Optional[str] = args.rules
    extra_macro_paths: List[str] = args.extra_macros
    extra_rule_paths: List[str] = args.extra_rules
    output_dir: str = args.output
    selinux_dir: Optional[str] = args.selinux
    partition_name: Optional[str] = None

    if selinux_dir is None:
        platform_policy: Optional[str] = args.platform

        assert args.policy is not None
        policy: str = args.policy

        version: Optional[str] = args.version
    else:
        platform_policy, policy, version, partition_name = (
            get_selinux_dir_policy(selinux_dir)
        )

    if not macro_paths:
        macro_paths = str(get_macros_path(version, args.current))

    if not rule_paths:
        rule_paths = macro_paths

    assert version is not None

    # TODO: parse technical debt files

    print(f'Found platform policy: {platform_policy}')
    print(f'Found policy: {policy}')
    print(f'Found policy version: {version}')

    conditional_types_map: Dict[str, ConditionalType] = {}
    missing_generated_types: Set[str] = set()

    # Load generated types and rules from platform policy
    platform_decompiled_rules = None
    if platform_policy is not None:
        platform_decompiled_rules, _ = decompile_one_cil(
            platform_policy,
            conditional_types_map,
            set(),
            version,
        )

    decompiled_rules, genfs_rules = decompile_one_cil(
        policy,
        conditional_types_map,
        missing_generated_types,
        version,
    )

    # Generate match dicts starting after the first token of the rule
    # which is almost always the type
    # This means that we can't match rules not knowing their type, but
    # that's fine usually
    mld: MultiLevelDict[Rule] = MultiLevelDict(RULE_DYNAMIC_PARTS_INDEX)
    for rule in decompiled_rules:
        # Add partial matches to this rule
        # Start partial matching after the first key
        mld.add(rule.hash_values, rule)

    # Add platform rules and remove them later to allow matching
    # set_prop(vendor_init, ...)
    # Since somehow allow vendor_init property_socket:sock_file write;
    # only ends up in platform sepolicy
    if platform_decompiled_rules is not None:
        for rule in platform_decompiled_rules:
            mld.add(rule.hash_values, rule)

    macro_file_paths, access_vectors_path, flagging_macros_path = (
        resolve_macro_paths(
            [macro_paths],
            system_sepolicy_path,
        )
    )
    extra_macro_file_paths, _, _ = resolve_macro_paths(extra_macro_paths)
    macro_file_paths += extra_macro_file_paths

    rule_file_paths = resolve_rule_paths(
        [rule_paths] + extra_rule_paths,
        system_sepolicy_path,
    )
    macro_file_paths += rule_file_paths

    print_macro_file_paths(macro_file_paths)
    print(f'Loading access vectors: {access_vectors_path}')

    macros_text = read_macros(macro_file_paths)

    all_variables_choices: Dict[str, Set[str]] = {}

    ifelse_variables_choices = gather_ifelse_variables(macros_text)
    all_variables_choices.update(ifelse_variables_choices)

    all_variables_choices['target_board_api_level'] = set([version])

    for k, v in default_variables.items():
        all_variables_choices[k] = set([v])

    for kv in args.var:
        k, v = kv.split('=')
        all_variables_choices[k] = v

    print('Using variables:')
    for k, vs in all_variables_choices.items():
        print(f'{k}={", ".join(vs)}')

    expanded_macros_text = expand_macro_bodies(
        macros_text,
        all_variables_choices,
    )

    (
        expanded_macros,
        class_sets,
        perms,
        ioctls,
        ioctl_defines,
        source_rule_texts,
    ) = categorize_macros(expanded_macros_text)

    decompiled_perms = decompile_perms(perms)
    decompiled_class_sets = decompile_perms(class_sets)
    decompiled_ioctls = decompile_ioctls(ioctls)
    decompiled_ioctl_defines = decompile_ioctl_defines(ioctl_defines)

    assert access_vectors_path is not None
    classmap = Classmap(flagging_macros_path, access_vectors_path, version)

    macros_name_rules = decompile_macros(classmap, expanded_macros)
    source_rules = decompile_rules(classmap, source_rule_texts)
    color_print(
        f'Found {len(source_rules)} source rules',
        color=Color.GREEN,
    )

    sort_macros(macros_name_rules)

    color_print(
        f'Found {len(mld)} prebuilt rules',
        color=Color.GREEN,
    )

    all_rule_matches: Set[RuleMatch] = set()
    for macro_name, macro_rules in macros_name_rules:
        match_macro_rules(
            mld,
            macro_name,
            macro_rules,
            all_rule_matches,
        )

    remove_rules_from_rule_matches(
        all_rule_matches,
        source_rules,
        'source',
    )

    if platform_decompiled_rules is not None:
        remove_rules_from_rule_matches(
            all_rule_matches,
            platform_decompiled_rules,
            'prebuilt platform',
        )

    replace_macro_rules(mld, all_rule_matches)

    def remove_platform_and_source_rules():
        if platform_decompiled_rules is not None:
            remove_rules(
                mld,
                platform_decompiled_rules,
                'prebuilt platform',
            )

        remove_rules(
            mld,
            source_rules,
            'source',
        )

    # Remove rules before and after merging ioctl rules, as source rules are
    # parsed properly, resulting in not-split ioctl rules, but the merging
    # logic for CIL rules is not entirely accurate, as it merges too eagerly
    # TODO: merge ioctls taking into account position
    # For example, see allowxperm installd ...
    remove_platform_and_source_rules()

    merge_ioctl_rules(mld)

    # See above
    remove_platform_and_source_rules()

    merge_typeattribute_rules(mld)

    replace_perms(mld, classmap, decompiled_perms)
    replace_ioctls(mld, decompiled_ioctls, decompiled_ioctl_defines)
    merge_class_sets(mld, decompiled_class_sets)

    # We can also merge target domains, but rules get long quickly
    # merge_target_domains(mld)

    color_print(f'Leftover rules: {len(mld)}', color=Color.GREEN)

    grouped_rules = group_rules(mld)

    shutil.rmtree(output_dir, ignore_errors=True)
    os.makedirs(output_dir)

    # TODO: remove contexts present in source rules
    output_contexts(selinux_dir, output_dir, partition_name)
    if genfs_rules:
        output_genfs_contexts(genfs_rules, output_dir)
    output_grouped_rules(grouped_rules, output_dir)


if __name__ == '__main__':
    decompile_cil()

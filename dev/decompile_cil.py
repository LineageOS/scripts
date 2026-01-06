#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import shutil
from argparse import ArgumentParser
from functools import partial
from itertools import chain
from pathlib import Path
from typing import Dict, List, Optional, Set

from sepolicy.cil_rule import CilRule
from sepolicy.classmap import Classmap
from sepolicy.conditional_type import ConditionalType
from sepolicy.contexts import (
    ContextsType,
    expand_contexts_texts,
    find_contexts_used_types,
    output_contexts,
    output_genfs_contexts,
    parse_contexts_texts,
    remove_source_contexts,
    remove_source_genfs_rules,
    resolve_contexts_paths,
    split_contexts_text,
)
from sepolicy.macro import (
    categorize_macros,
    expand_macro_bodies,
    macro_name_body_raw,
    macro_used_variables,
    parse_ioctl_defines,
    parse_ioctls,
    parse_macros,
    parse_perms,
    resolve_macro_paths,
    split_ioctl_defines,
    split_macros_text,
)
from sepolicy.match import (
    discard_rule_matches,
    find_public_rules,
    find_used_types,
    match_macros_rules,
    merge_class_sets,
    merge_ioctl_rules,
    merge_typeattribute_rules,
    remove_rules,
    remove_rules_from_rule_matches,
    remove_unused_types,
    replace_ioctls,
    replace_macro_rules,
    replace_perms,
)
from sepolicy.output import (
    group_rules,
    output_grouped_rules,
)
from sepolicy.rule import RULE_DYNAMIC_PARTS_INDEX, Rule
from sepolicy.rules import parse_rules, resolve_rule_paths
from utils.mld import MultiLevelDict
from utils.utils import Color, android_root, color_print

system_sepolicy_path = Path(android_root, 'system/sepolicy')


def get_macros_paths(version: str, current: bool):
    if current:
        return [system_sepolicy_path]

    return [
        Path(system_sepolicy_path, f'prebuilts/api/{version}'),
    ]


def get_rules_paths(version: Optional[str], current: bool):
    vendor_sepolicy_path = Path(system_sepolicy_path, 'vendor')
    if current:
        return [
            system_sepolicy_path,
            vendor_sepolicy_path,
        ]

    return [
        Path(system_sepolicy_path, f'prebuilts/api/{version}'),
        # Vendor sepolicy is not versioned, this is a best effort
        vendor_sepolicy_path,
    ]


def get_variable_choices(
    args_variables: List[str],
    macros_texts: List[List[str]],
    contexts_texts: Dict[ContextsType, List[str]],
    version: str,
):
    all_variables_choices: Dict[str, Set[str]] = {}

    # Find conditional variables used in the input text
    # Conditional variables can be specified, but we need to know if the
    # macro arguments are used in them
    for macros_text in macros_texts:
        for macro_text in macros_text:
            name, body = macro_name_body_raw(macro_text)
            conditional_variables = macro_used_variables(name, body)
            all_variables_choices.update(conditional_variables)

    for context_texts in contexts_texts.values():
        for context_text in context_texts:
            conditional_variables = macro_used_variables(None, context_text)
            all_variables_choices.update(conditional_variables)

    # Variables extracted from system/sepolicy/build/soong/policy.go
    all_variables_choices['mls_num_sens'] = set(['1'])
    all_variables_choices['mls_num_cats'] = set(['1024'])

    all_variables_choices['target_board_api_level'] = set([version])

    for kv in args_variables:
        k, v = kv.split('=')
        if k not in all_variables_choices:
            all_variables_choices[k] = set()

        all_variables_choices[k].add(v)

    print('Using variables:')
    for k, vs in all_variables_choices.items():
        print(f'{k}={", ".join(vs)}')

    return all_variables_choices


def decompile_one_cil(
    cil_path: Path,
    conditional_types_map: Dict[str, ConditionalType],
    missing_generated_types: Set[str],
    version: Optional[str],
    name: str,
):
    cil_data = cil_path.read_text()
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

    # ioctl rules are split at comments / newlines by the compiler
    # merge adjacent ioctl rules of the same type back
    # TODO: this won't work if the rules end up next to eachother but
    # they weren't next to eachother initially, but the chances for that
    # are very low
    rules = merge_ioctl_rules(rules, name)

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


def get_selinux_dir_policy(selinux_dir: Path):
    partition_root = selinux_dir.parent.parent
    partition_name = partition_root.name
    dump_root = partition_root.parent

    vendor_policy_path = Path(dump_root, 'vendor/etc/selinux')
    system_policy_path = Path(dump_root, 'system/etc/selinux')
    platform_build_prop_path = Path(dump_root, 'system/build.prop')

    split_public_private = False
    referencing_policy_path = None
    referencing_policy_version = None

    # Read policy for vendor / odm
    # For system / system_ext / product, this is used to find public
    # types
    # For vendor / odm, this is loaded to allow proper macro resolution
    versioned_platform_policy_path = Path(
        vendor_policy_path,
        'plat_pub_versioned.cil',
    )
    assert versioned_platform_policy_path.exists(), (
        versioned_platform_policy_path
    )

    # Read policy version for vendor / odm
    versioned_platform_policy_version_path = Path(
        vendor_policy_path,
        'plat_sepolicy_vers.txt',
    )
    assert versioned_platform_policy_version_path.exists(), (
        versioned_platform_policy_version_path
    )
    versioned_platform_policy_version = (
        versioned_platform_policy_version_path.read_text().strip()
    )

    if partition_name in ['vendor', 'odm']:
        platform_policy_path = versioned_platform_policy_path
        policy_version = versioned_platform_policy_version
    else:
        platform_policy_path = Path(
            system_policy_path,
            'plat_sepolicy.cil',
        )
        assert platform_policy_path.exists(), platform_policy_path

        policy_version = get_sdk_value(platform_build_prop_path)

        split_public_private = True
        referencing_policy_path = versioned_platform_policy_path
        referencing_policy_version = versioned_platform_policy_version

    if partition_name == 'system':
        partition_name = 'plat'
        platform_policy_path = None

    policy_path = Path(selinux_dir, f'{partition_name}_sepolicy.cil')

    assert policy_path.exists(), policy_path
    assert policy_version is not None

    return (
        platform_policy_path,
        policy_path,
        policy_version,
        partition_name,
        split_public_private,
        referencing_policy_path,
        referencing_policy_version,
    )


def decompile_cil():
    parser = ArgumentParser(
        prog='decompile_cil.py',
        description='Decompile CIL files',
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Verbose output',
    )
    parser.add_argument(
        '--current',
        action='store_true',
        help='Use current macros (rather than versioned macros)',
    )
    parser.add_argument(
        '-s',
        '--selinux',
        action='store',
        required=True,
        help='Path to selinux directory (eg: vendor/etc/selinux)',
    )
    parser.add_argument(
        '-m',
        '--macros',
        action='append',
        default=[],
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
        default=[],
        help='Path to files or directories containing rules and contexts to be removed '
        '(eg: system/sepolicy/prebuilts/api/31.0), '
        'will default to the macros path if not specified',
    )
    parser.add_argument(
        '--extra-rules',
        action='append',
        default=[],
        help='Path to files or directories containing extra rules and contexts to be removed '
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

    current_policy: bool = args.current
    verbose: bool = args.verbose
    macros_paths = [Path(s) for s in args.macros]
    rules_paths = [Path(s) for s in args.rules]
    extra_macros_paths = [Path(s) for s in args.extra_macros]
    extra_rules_paths = [Path(s) for s in args.extra_rules]
    output_dir = Path(args.output)
    selinux_dir = Path(args.selinux)
    (
        platform_policy,
        policy,
        version,
        partition_name,
        split_public_private,
        referencing_policy_path,
        referencing_policy_version,
    ) = get_selinux_dir_policy(
        selinux_dir,
    )

    if not macros_paths:
        macros_paths = get_macros_paths(version, current_policy)

    if not rules_paths:
        rules_paths = get_rules_paths(version, current_policy)

    print(f'Found platform policy: {platform_policy}')
    print(f'Found policy: {policy}')
    print(f'Found policy version: {version}')
    if referencing_policy_path is not None:
        print(f'Found referencing policy: {referencing_policy_path}')
    if referencing_policy_version is not None:
        print(f'Found referencing policy version: {referencing_policy_version}')

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
            'platform policy',
        )

    # Load rules being referenced by other sepolicy which need to be
    # public
    referencing_rules = None
    if split_public_private:
        assert referencing_policy_path is not None
        assert referencing_policy_version is not None

        referencing_rules, _ = decompile_one_cil(
            referencing_policy_path,
            {},
            set(),
            referencing_policy_version,
            'referencing policy',
        )

    # Find all used types and remove all unused ones
    decompiled_used_types: Set[str] = set()

    decompiled_rules, decompiled_genfs_rules = decompile_one_cil(
        policy,
        conditional_types_map,
        missing_generated_types,
        version,
        'decompiled policy',
    )
    decompiled_contexts_file_paths = resolve_contexts_paths(
        [selinux_dir],
        partition_name,
        None,
        verbose,
    )
    decompiled_contexts_texts = split_contexts_text(
        decompiled_contexts_file_paths,
    )
    decompiled_contexts, _ = parse_contexts_texts(
        decompiled_contexts_texts,
    )

    find_used_types(decompiled_rules, decompiled_used_types)
    find_used_types(decompiled_genfs_rules, decompiled_used_types)
    find_contexts_used_types(decompiled_contexts, decompiled_used_types)

    # Generate match dicts starting after the first token of the rule
    # which is almost always the type
    # This means that we can't match rules not knowing their type, but
    # that's fine usually
    mld: MultiLevelDict[Rule] = MultiLevelDict(RULE_DYNAMIC_PARTS_INDEX)

    # Add all public rules into a separate dictionary to be able to group them
    # and do the same processing as private rules
    public_mld: MultiLevelDict[Rule] = MultiLevelDict(RULE_DYNAMIC_PARTS_INDEX)

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

    # TODO: get rid of this, as it is only necessary because some of the types
    # in system_ext end up in product, but it's not all of the public types,
    # as some types end up in vendor's versioned policy while they do not end up
    # in product
    remove_unused_types(mld, decompiled_used_types)

    public_types: Set[str] = set()
    public_rules: List[Rule] = []
    if split_public_private:
        assert referencing_rules is not None
        public_rules = find_public_rules(mld, referencing_rules, public_types)

    (
        macro_file_paths,
        ioctl_defines_file_paths,
        nlmsg_defines_file_paths,
        technical_debt_path,
        access_vectors_path,
        flagging_macros_path,
    ) = resolve_macro_paths(
        macros_paths + extra_macros_paths,
        system_sepolicy_path,
        verbose,
    )

    rule_file_paths = resolve_rule_paths(
        rules_paths + extra_rules_paths,
        system_sepolicy_path,
        verbose,
    )

    macro_file_paths += rule_file_paths
    macros_texts = split_macros_text(macro_file_paths)
    ioctl_defines_texts = split_macros_text(ioctl_defines_file_paths)
    nlmsg_defines_texts = split_macros_text(nlmsg_defines_file_paths)

    source_contexts_file_paths = resolve_contexts_paths(
        rules_paths + extra_rules_paths,
        None,
        system_sepolicy_path,
        verbose,
    )
    source_contexts_texts = split_contexts_text(
        source_contexts_file_paths,
    )

    all_variables_choices = get_variable_choices(
        args.var,
        [macros_texts, ioctl_defines_texts, nlmsg_defines_texts],
        source_contexts_texts,
        version,
    )

    expanded_ioctl_defines_text = expand_macro_bodies(
        ioctl_defines_texts,
        all_variables_choices,
        macros_handled_elsewhere=set(),
    )

    expanded_nlmsg_defines_text = expand_macro_bodies(
        nlmsg_defines_texts,
        all_variables_choices,
        macros_handled_elsewhere=set(),
    )

    ioctl_defines = split_ioctl_defines(expanded_ioctl_defines_text)
    nlmsg_defines = split_ioctl_defines(expanded_nlmsg_defines_text)

    # Prevent expand_macro_bodies() from expanding and assigning ioctls and
    # nlmsgs again, while also providing them for expansion
    ioctl_nlmsg_defines_names = set(
        name
        for name, _ in chain(
            ioctl_defines,
            nlmsg_defines,
        )
    )

    expanded_macros_text = expand_macro_bodies(
        macros_texts,
        all_variables_choices,
        macros_handled_elsewhere=ioctl_nlmsg_defines_names,
    )

    expanded_source_contexts_texts = expand_contexts_texts(
        source_contexts_texts,
        all_variables_choices,
        flagging_macros_path,
        version,
    )

    source_contexts, source_genfs_rules = parse_contexts_texts(
        expanded_source_contexts_texts,
    )

    (
        expanded_macros,
        class_sets,
        perms,
        ioctls,
        nlmsgs,
        source_rule_texts,
    ) = categorize_macros(expanded_macros_text)

    source_perms = parse_perms(perms)
    source_class_sets = parse_perms(class_sets)
    source_ioctls = parse_ioctls(ioctls, is_nlmsg=False)
    source_nlmsgs = parse_ioctls(nlmsgs, is_nlmsg=True)
    source_ioctl_defines = parse_ioctl_defines(
        ioctl_defines,
        verbose,
        is_nlmsg=False,
    )
    source_nlmsg_defines = parse_ioctl_defines(
        nlmsg_defines,
        verbose,
        is_nlmsg=True,
    )

    classmap = Classmap(flagging_macros_path, version, access_vectors_path)
    macros_name_rules = parse_macros(classmap, expanded_macros)
    source_rules = parse_rules(classmap, source_rule_texts)

    if technical_debt_path is not None:
        source_technical_debt_rules, _ = decompile_one_cil(
            technical_debt_path,
            {},
            set(),
            version,
            'source technical debt policy',
        )
        source_rules += source_technical_debt_rules

    # This rule is automatically added by
    # external/selinux/libsepol/src/module_to_cil.c
    source_rules.append(Rule('attribute', ('cil_gen_require',), ()))

    color_print(
        f'Found {len(source_rules)} source rules',
        color=Color.GREEN,
    )

    def count_decompiled_rules():
        num_decompiled_contexts = sum(
            len(c) for c in decompiled_contexts.values()
        )
        num_decompiled_rules = (
            len(mld)
            + len(public_mld)
            + len(decompiled_genfs_rules)
            + num_decompiled_contexts
        )
        return num_decompiled_rules

    color_print(
        f'Found {count_decompiled_rules()} prebuilt rules',
        color=Color.GREEN,
    )

    rule_matches = match_macros_rules(
        mld,
        macros_name_rules,
        verbose,
    )
    rule_matches = discard_rule_matches(rule_matches, verbose)

    rule_matches = remove_rules_from_rule_matches(
        rule_matches,
        source_rules,
        'source',
    )

    if platform_decompiled_rules is not None:
        rule_matches = remove_rules_from_rule_matches(
            rule_matches,
            platform_decompiled_rules,
            'prebuilt platform',
        )

    def process_rules(
        m: MultiLevelDict[Rule],
        name: str,
        remove_public: bool,
    ):
        remove_rules(
            m,
            source_rules,
            'source',
            name,
        )

        if platform_decompiled_rules is not None:
            remove_rules(
                m,
                platform_decompiled_rules,
                'prebuilt platform',
                name,
            )

        if remove_public:
            remove_rules(
                m,
                public_rules,
                'public',
                name,
            )

        replace_macro_rules(
            m,
            rule_matches,
            name,
            verbose,
        )

        merge_typeattribute_rules(m, name)

        replace_perms(m, classmap, source_perms, name)
        replace_ioctls(
            m,
            source_ioctls,
            source_ioctl_defines,
            name,
            is_nlmsg=False,
        )
        replace_ioctls(
            m,
            source_nlmsgs,
            source_nlmsg_defines,
            name,
            is_nlmsg=True,
        )
        merge_class_sets(m, source_class_sets, name)

        # We can also merge target domains, but rules get long quickly
        # merge_target_domains(m)

    process_rules(mld, 'private', remove_public=True)

    if split_public_private:
        for public_rule in public_rules:
            public_mld.add(public_rule.hash_values, public_rule)

    process_rules(public_mld, 'public', remove_public=False)

    # Remove decompiled contexts also found in the source contexts
    decompiled_contexts = remove_source_contexts(
        decompiled_contexts,
        source_contexts,
    )
    decompiled_genfs_rules = remove_source_genfs_rules(
        decompiled_genfs_rules,
        source_genfs_rules,
    )

    color_print(
        f'Leftover rules: {count_decompiled_rules()}', color=Color.GREEN
    )

    grouped_rules = group_rules(mld)
    public_grouped_rules = group_rules(public_mld)

    shutil.rmtree(output_dir, ignore_errors=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    if split_public_private:
        private_output_dir = Path(output_dir, 'private')
        private_output_dir.mkdir(parents=True, exist_ok=True)
    else:
        private_output_dir = output_dir

    output_contexts(decompiled_contexts, private_output_dir)
    output_genfs_contexts(decompiled_genfs_rules, private_output_dir)
    output_grouped_rules(grouped_rules, rule_matches, private_output_dir)

    if split_public_private:
        public_output_dir = Path(output_dir, 'public')
        public_output_dir.mkdir(parents=True, exist_ok=True)
        output_grouped_rules(
            public_grouped_rules, rule_matches, public_output_dir
        )


if __name__ == '__main__':
    decompile_cil()

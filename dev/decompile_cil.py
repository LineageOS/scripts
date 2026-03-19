#!/usr/bin/env python3
# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import shutil
from argparse import ArgumentParser
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from sepolicy.cil_policy import decompile_one_cil
from sepolicy.conditional_type import ConditionalType
from sepolicy.contexts import (
    ContextsType,
    find_contexts_used_types,
    output_contexts,
    output_genfs_contexts,
    parse_contexts_texts,
    remove_source_contexts,
    remove_source_genfs_rules,
    resolve_contexts_paths,
    split_contexts_text,
)
from sepolicy.match import (
    RuleMatch,
    discard_rule_matches,
    find_public_rules,
    find_used_types,
    match_macros_rules,
    process_rules,
    remove_rules_from_rule_matches,
    remove_unused_types,
)
from sepolicy.output import (
    group_rules,
    output_grouped_rules,
)
from sepolicy.policy_info import get_selinux_dir_policy
from sepolicy.rule import RULE_DYNAMIC_PARTS_INDEX, Rule
from sepolicy.source_policy import ParsedSource, parse_source
from utils.mld import MultiLevelDict
from utils.utils import Color, android_root, color_print

system_sepolicy_path = Path(android_root, 'system/sepolicy')


def count_decompiled_rules(
    mld: MultiLevelDict[Rule],
    decompiled_contexts: Optional[
        Dict[
            ContextsType,
            List[Tuple[str, ...]],
        ]
    ],
    decompiled_genfs_rules: Optional[List[Rule]],
):
    num_decompiled_contexts = sum(
        len(c) for c in (decompiled_contexts or {}).values()
    )
    num_decompiled_rules = (
        len(mld) + len(decompiled_genfs_rules or []) + num_decompiled_contexts
    )
    return num_decompiled_rules


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


def process_output_rules(
    mld: MultiLevelDict[Rule],
    genfs_rules: Optional[List[Rule]],
    contexts: Optional[Dict[ContextsType, List[Tuple[str, ...]]]],
    removed_rules: List[Tuple[str, List[Rule]]],
    output_dir: Path,
    rule_matches: List[RuleMatch],
    source: ParsedSource,
    verbose: bool,
    name: str,
):
    process_rules(
        mld,
        source=source,
        removed_rules=removed_rules,
        rule_matches=rule_matches,
        name=name,
        verbose=verbose,
    )

    # Remove decompiled contexts also found in the source contexts
    if contexts is not None:
        contexts = remove_source_contexts(
            contexts,
            source.contexts,
        )

    if genfs_rules is not None:
        genfs_rules = remove_source_genfs_rules(
            genfs_rules,
            source.genfs_rules,
        )

    count = count_decompiled_rules(
        mld,
        contexts,
        genfs_rules,
    )
    color_print(f'Leftover {name} rules: {count}', color=Color.GREEN)

    grouped_rules = group_rules(mld)

    if contexts is not None:
        output_contexts(contexts, output_dir)
    if genfs_rules is not None:
        output_genfs_contexts(genfs_rules, output_dir)
    output_grouped_rules(grouped_rules, rule_matches, output_dir)


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

    policy_info = get_selinux_dir_policy(selinux_dir)

    if not macros_paths:
        macros_paths = get_macros_paths(policy_info.version, current_policy)

    if not rules_paths:
        rules_paths = get_rules_paths(policy_info.version, current_policy)

    print(f'Found platform policy: {policy_info.platform_policy_path}')
    print(f'Found policy: {policy_info.policy_path}')
    print(f'Found policy version: {policy_info.version}')
    if policy_info.referencing_policy_path is not None:
        print(
            f'Found referencing policy: {policy_info.referencing_policy_path}'
        )
    if policy_info.referencing_policy_version is not None:
        print(
            f'Found referencing policy version: '
            f'{policy_info.referencing_policy_version}'
        )

    conditional_types_map: Dict[str, ConditionalType] = {}
    missing_generated_types: Set[str] = set()

    decompiled_rules, decompiled_genfs_rules = decompile_one_cil(
        policy_info.policy_path,
        conditional_types_map,
        missing_generated_types,
        policy_info.version,
        'decompiled policy',
    )

    # Generate match dicts starting after the first token of the rule
    # which is almost always the type
    # This means that we can't match rules not knowing their type, but
    # that's fine usually
    mld: MultiLevelDict[Rule] = MultiLevelDict(RULE_DYNAMIC_PARTS_INDEX)
    mld.add_many(decompiled_rules, lambda r: r.hash_values)

    # Load generated types and rules from platform policy
    # Add platform rules and remove them later to allow matching
    # set_prop(vendor_init, ...)
    # Since somehow allow vendor_init property_socket:sock_file write;
    # only ends up in platform sepolicy
    platform_decompiled_rules = None
    if policy_info.platform_policy_path is not None:
        platform_decompiled_rules, _ = decompile_one_cil(
            policy_info.platform_policy_path,
            conditional_types_map,
            set(),
            policy_info.version,
            'platform policy',
        )
        mld.add_many(platform_decompiled_rules, lambda r: r.hash_values)

    decompiled_contexts_file_paths = resolve_contexts_paths(
        [selinux_dir],
        policy_info.partition_name,
        None,
        verbose,
    )
    decompiled_contexts_texts = split_contexts_text(
        decompiled_contexts_file_paths,
    )
    decompiled_contexts, _ = parse_contexts_texts(
        decompiled_contexts_texts,
    )

    # Find all used types and remove all unused ones
    decompiled_used_types: Set[str] = set()
    find_used_types(decompiled_rules, decompiled_used_types)
    find_used_types(decompiled_genfs_rules, decompiled_used_types)
    find_contexts_used_types(decompiled_contexts, decompiled_used_types)

    # TODO: get rid of this, as it is only necessary because some of the types
    # in system_ext end up in product, but it's not all of the public types,
    # as some types end up in vendor's versioned policy while they do not end up
    # in product
    remove_unused_types(mld, decompiled_used_types)

    public_rules: List[Rule] = []
    if policy_info.split_public_private:
        assert policy_info.referencing_policy_path is not None
        assert policy_info.referencing_policy_version is not None

        # Load rules being referenced by other sepolicy which need to be
        # public
        referencing_rules, _ = decompile_one_cil(
            policy_info.referencing_policy_path,
            {},
            set(),
            policy_info.referencing_policy_version,
            'referencing policy',
        )

        public_rules = find_public_rules(mld, referencing_rules)

    source = parse_source(
        macros_paths,
        extra_macros_paths,
        rules_paths,
        extra_rules_paths,
        system_sepolicy_path,
        args.var,
        verbose,
        policy_info.version,
    )

    color_print(f'Found {len(source.rules)} source rules', color=Color.GREEN)

    count = count_decompiled_rules(
        mld,
        decompiled_contexts,
        decompiled_genfs_rules,
    )
    color_print(f'Found {count} prebuilt rules', color=Color.GREEN)

    rule_matches = match_macros_rules(
        mld,
        source.macros_name_rules,
        verbose,
    )
    rule_matches = discard_rule_matches(rule_matches, verbose)

    rule_matches = remove_rules_from_rule_matches(
        rule_matches,
        source.rules,
        'source',
    )

    if platform_decompiled_rules is not None:
        rule_matches = remove_rules_from_rule_matches(
            rule_matches,
            platform_decompiled_rules,
            'prebuilt platform',
        )

    shutil.rmtree(output_dir, ignore_errors=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    private_output_dir = output_dir
    if policy_info.split_public_private:
        private_output_dir = Path(output_dir, 'private')
        private_output_dir.mkdir(parents=True, exist_ok=True)

    process_output_rules(
        mld=mld,
        genfs_rules=decompiled_genfs_rules,
        contexts=decompiled_contexts,
        removed_rules=[
            ('source', source.rules),
            ('prebuilt platform', platform_decompiled_rules or []),
            ('public', public_rules),
        ],
        output_dir=private_output_dir,
        rule_matches=rule_matches,
        source=source,
        verbose=verbose,
        name='private',
    )

    if policy_info.split_public_private:
        public_output_dir = Path(output_dir, 'public')
        public_output_dir.mkdir(parents=True, exist_ok=True)

        # Add all public rules into a separate dictionary to be able to group them
        # and do the same processing as private rules
        public_mld = MultiLevelDict[Rule](RULE_DYNAMIC_PARTS_INDEX)
        public_mld.add_many(public_rules, lambda r: r.hash_values)

        process_output_rules(
            mld=public_mld,
            genfs_rules=None,
            contexts=None,
            output_dir=public_output_dir,
            removed_rules=[
                ('source', source.rules),
                ('prebuilt platform', platform_decompiled_rules or []),
            ],
            rule_matches=rule_matches,
            source=source,
            verbose=verbose,
            name='public',
        )


if __name__ == '__main__':
    decompile_cil()

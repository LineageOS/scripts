#!/usr/bin/env python3
# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import shutil
from argparse import ArgumentParser
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from sepolicy.cil_policy import parse_prebuilt
from sepolicy.contexts import (
    ContextsType,
    output_contexts,
    output_genfs_contexts,
    remove_source_contexts,
    remove_source_genfs_rules,
)
from sepolicy.match import (
    RuleMatch,
    discard_rule_matches,
    match_macros_rules,
    process_rules,
    remove_unused_types,
)
from sepolicy.output import (
    group_rules,
    output_grouped_rules,
)
from sepolicy.policy_info import get_selinux_dir_policy
from sepolicy.rule import Rule
from sepolicy.source_policy import SourcePolicy, parse_source
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
    removed_rules: List[Tuple[str, Iterable[Rule]]],
    output_dir: Path,
    rule_matches: List[RuleMatch],
    source: SourcePolicy,
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
        '--extra-macros',
        action='append',
        default=[],
        help='Path to files or directories containing extra macros',
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
    extra_macros_paths = [Path(s) for s in args.extra_macros]
    extra_rules_paths = [Path(s) for s in args.extra_rules]
    output_dir = Path(args.output)
    selinux_dir = Path(args.selinux)

    policy_info = get_selinux_dir_policy(selinux_dir)
    macros_paths = get_macros_paths(policy_info.version, current_policy)
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

    prebuilt = parse_prebuilt(policy_info, verbose)

    # TODO: get rid of this, as it is only necessary because some of the types
    # in system_ext end up in product, but it's not all of the public types,
    # as some types end up in vendor's versioned policy while they do not end up
    # in product
    remove_unused_types(prebuilt.mld, prebuilt.used_types)

    count = count_decompiled_rules(
        prebuilt.mld,
        prebuilt.contexts,
        prebuilt.genfs_rules,
    )
    color_print(f'Found {count} prebuilt rules', color=Color.GREEN)

    rule_matches = match_macros_rules(
        prebuilt.mld,
        source.macros_name_rules,
        verbose,
    )
    rule_matches = discard_rule_matches(rule_matches, verbose)

    shutil.rmtree(output_dir, ignore_errors=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    private_output_dir = output_dir
    if policy_info.split_public_private:
        private_output_dir = Path(output_dir, 'private')
        private_output_dir.mkdir(parents=True, exist_ok=True)

    process_output_rules(
        mld=prebuilt.mld,
        genfs_rules=prebuilt.genfs_rules,
        contexts=prebuilt.contexts,
        removed_rules=[
            ('source', source.rules),
            *prebuilt.extra_rules,
            ('public', prebuilt.public_mld),
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

        process_output_rules(
            mld=prebuilt.public_mld,
            genfs_rules=None,
            contexts=None,
            output_dir=public_output_dir,
            removed_rules=[
                ('source', source.rules),
                *prebuilt.extra_rules,
            ],
            rule_matches=rule_matches,
            source=source,
            verbose=verbose,
            name='public',
        )


if __name__ == '__main__':
    decompile_cil()

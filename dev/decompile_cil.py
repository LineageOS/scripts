#!/usr/bin/env python3
# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import shutil
from argparse import ArgumentParser
from pathlib import Path
from typing import Dict, List

from sepolicy.cil_policy import parse_dump_policies
from sepolicy.contexts import (
    output_contexts,
    output_genfs_contexts,
    remove_source_contexts,
    remove_source_genfs_rules,
)
from sepolicy.match import (
    RuleMatch,
    discard_rule_matches,
    match_macros_rules,
    merge_class_sets,
    merge_typeattribute_rules,
    replace_macro_rules,
)
from sepolicy.output import group_rules, output_grouped_rules
from sepolicy.policy import (
    Policy,
    PolicyName,
    PolicyParsedOrigin,
    get_hardcoded_policy,
)
from sepolicy.rule_container import RuleContainer
from sepolicy.source_policy import Source, SourceIndex
from utils.utils import Color, color_print


def split_policy_in_out(
    policy: Policy,
    other_policy: Policy,
    in_name: PolicyName,
    out_name: PolicyName,
):
    assert not other_policy.contexts, other_policy.contexts
    assert not other_policy.genfs_rules, other_policy.genfs_rules

    in_other_rules = RuleContainer(sparse_match=True)
    out_other_rules = RuleContainer(sparse_match=True)

    for rule in policy.rules:
        if rule in other_policy.rules:
            in_other_rules.add(rule)
        else:
            out_other_rules.add(rule)

    return (
        Policy(
            name=in_name,
            rules=in_other_rules,
            contexts={},
            genfs_rules=RuleContainer(),
            metadata=policy.metadata,
        ),
        Policy(
            name=out_name,
            rules=out_other_rules,
            contexts=policy.contexts,
            genfs_rules=policy.genfs_rules,
            metadata=policy.metadata,
        ),
    )


def process_policy_post_split(
    policy: Policy,
    policy_index: Dict[PolicyName, Policy],
    rule_matches: List[RuleMatch],
    source: Source,
    output_dir: Path,
    verbose: bool,
):
    print(f'Replacing in {policy.pretty_name}')

    assert policy.type.output is not None

    rules = RuleContainer(policy.rules, sparse_match=True)
    contexts = policy.contexts
    genfs_rules = policy.genfs_rules

    for policy_name in policy.type.output.cleanup_policy:
        cleanup_policy = policy_index[policy_name]
        print(f'Removing policy {cleanup_policy} from {policy.pretty_name}')

        removed_rules = rules.remove_many(
            cleanup_policy.rules,
            optional=True,
        )
        contexts, removed_contexts = remove_source_contexts(
            contexts,
            cleanup_policy.contexts,
        )
        genfs_rules, removed_genfs_rules = remove_source_genfs_rules(
            genfs_rules,
            cleanup_policy.genfs_rules,
        )

        color_print(
            f'Removed {removed_rules} rules from {policy.pretty_name}',
            color=Color.GREEN,
        )
        color_print(
            f'Removed {removed_contexts} contexts from {policy.pretty_name}',
            color=Color.GREEN,
        )
        color_print(
            f'Removed {removed_genfs_rules} genfs rules from {policy.pretty_name}',
            color=Color.GREEN,
        )

    replace_macro_rules(
        rules,
        rule_matches,
        policy.pretty_name,
        verbose,
    )

    merge_typeattribute_rules(
        rules,
        policy.pretty_name,
    )

    merge_class_sets(
        rules,
        source.macros.class_sets,
        policy.pretty_name,
    )

    # We can also merge target domains, but rules get long quickly
    # merge_target_domains(policy.rules)

    color_print(f'Leftover policy: {policy}', color=Color.GREEN)

    policy_output_dir = Path(output_dir, policy.type.output.relative_dir)
    policy_output_dir.mkdir(parents=True, exist_ok=True)

    output_contexts(contexts, policy_output_dir)
    output_genfs_contexts(genfs_rules, policy_output_dir)

    grouped_rules = group_rules(rules)
    output_grouped_rules(
        grouped_rules,
        rule_matches,
        source=source,
        output_dir=policy_output_dir,
    )


def process_policy_pre_split(
    policy: Policy,
    policy_index: Dict[PolicyName, Policy],
    source: Source,
    output_dir: Path,
    verbose: bool,
):
    print(f'Processing {policy.pretty_name}')

    assert isinstance(policy.type.origin, PolicyParsedOrigin)

    if policy.type.output is None and policy.type.referencing is None:
        print(f'Skipping {policy.pretty_name}')
        return

    rule_matches = match_macros_rules(
        policy.rules,
        source.macros.macros_name_rules,
        verbose,
    )
    rule_matches = discard_rule_matches(rule_matches, verbose)

    if policy.type.referencing is None:
        process_policy_post_split(
            policy,
            policy_index,
            rule_matches,
            source,
            output_dir,
            verbose,
        )
        return

    referencing_policy = policy_index[policy.type.referencing.name]

    print(f'Splitting {policy.pretty_name}')

    split_policies = split_policy_in_out(
        policy,
        referencing_policy,
        in_name=policy.type.referencing.in_name,
        out_name=policy.type.referencing.out_name,
    )

    for split_policy in split_policies:
        process_policy_post_split(
            split_policy,
            policy_index,
            rule_matches,
            source,
            output_dir,
            verbose,
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
        help='Use current macros',
    )
    parser.add_argument(
        '-d',
        '--dump',
        action='store',
        required=True,
        help='Path to dump to extract selinux from',
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
    dump_dir = Path(args.dump)

    source_index = SourceIndex(
        extra_rules_paths=extra_rules_paths,
        extra_macros_paths=extra_macros_paths,
        current=current_policy,
        verbose=verbose,
    )

    hardcoded_policy_index = {p.name: p for p in get_hardcoded_policy()}

    cil_policy_index = parse_dump_policies(dump_dir, source_index, verbose)
    for policy in cil_policy_index.values():
        print(f'Found policy: {policy}')
        print()

    shutil.rmtree(output_dir, ignore_errors=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    for policy in cil_policy_index.values():
        assert policy.metadata is not None
        source = source_index.get_source_policy(policy.metadata)
        policy_index = (
            cil_policy_index | hardcoded_policy_index | source.policy_index
        )

        process_policy_pre_split(
            policy=policy,
            policy_index=policy_index,
            source=source,
            output_dir=output_dir,
            verbose=verbose,
        )


if __name__ == '__main__':
    decompile_cil()

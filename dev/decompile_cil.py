#!/usr/bin/env python3
# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import shutil
from argparse import ArgumentParser
from pathlib import Path
from typing import List

from sepolicy.add_policy_provider import AddPolicyProvider
from sepolicy.binary_compiled_policy_provider import (
    BinaryCompiledPolicyProvider,
)
from sepolicy.cleanup_policy_provider import CleanupPolicyProvider
from sepolicy.combined_policy_provider import CombinedPolicyProvider
from sepolicy.compiled_policy_provider import CompiledPolicyProvider
from sepolicy.contexts import (
    output_contexts,
    output_genfs_contexts,
)
from sepolicy.dump_binary_policy_provider import DumpBinaryPolicyProvider
from sepolicy.dump_cil_policy_provider import DumpCilPolicyProvider
from sepolicy.expanded_guard_policy_provider import (
    ExpandedGuardPolicyProvider,
)
from sepolicy.gather_source_text_policy_provider import (
    GatherSourceTextPolicyProvider,
)
from sepolicy.hardcoded_policy_provider import HardcodedPolicyProvider
from sepolicy.macro_match_policy_provider import MacroMatchPolicyProvider
from sepolicy.macro_replace_policy_provider import MacroReplacePolicyProvider
from sepolicy.output import group_rules, output_grouped_rules
from sepolicy.policy import (
    Policy,
    PolicyIndex,
    get_policy_types,
    source_cleanup,
)
from sepolicy.referenced_policy_provider import ReferencedPolicyProvider
from sepolicy.source_cil_policy_provider import SourceCilPolicyProvider
from sepolicy.source_te_policy_provider import SourceTePolicyProvider


def to_paths(paths: List[str]) -> List[Path]:
    return [Path(p) for p in paths]


def process_policy_output(
    policy: Policy,
    output_dir: Path,
):
    print(f'Outputting {policy.pretty_name}')

    assert policy.type.output is not None

    policy_output_dir = Path(output_dir, policy.type.output.relative_dir)
    policy_output_dir.mkdir(parents=True, exist_ok=True)

    output_contexts(policy.contexts, policy_output_dir)
    output_genfs_contexts(policy.genfs_rules, policy_output_dir)

    grouped_rules = group_rules(policy.rules, policy.guarded_rules)
    output_grouped_rules(
        grouped_rules,
        macros=policy.macros,
        output_dir=policy_output_dir,
        rule_guard=policy.guarded_rules,
        mark_source=policy.rules,
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
        metavar='PATH',
        help='Path to files or directories containing extra macros',
    )
    parser.add_argument(
        '--cleanup-rules',
        action='append',
        default=[],
        metavar='PATH',
        help='Path to files or directories with rules to remove from the output',
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
    extra_macros_paths = {None: to_paths(args.extra_macros)}
    extra_rules_paths = {source_cleanup.name: to_paths(args.cleanup_rules)}
    output_dir = Path(args.output)
    dump_dir = Path(args.dump)

    policy_index = PolicyIndex()
    policy_index.register(HardcodedPolicyProvider())
    policy_index.register(ReferencedPolicyProvider())
    policy_index.register(
        SourceTePolicyProvider(
            extra_rules_paths=extra_rules_paths,
            extra_macros_paths=extra_macros_paths,
            current=current_policy,
            verbose=verbose,
        )
    )
    policy_index.register(
        SourceCilPolicyProvider(
            current=current_policy,
            verbose=verbose,
        )
    )
    policy_index.register(
        DumpCilPolicyProvider(
            dump_root=dump_dir,
            verbose=verbose,
        )
    )
    policy_index.register(
        DumpBinaryPolicyProvider(
            dump_root=dump_dir,
            verbose=verbose,
        )
    )
    policy_index.register(AddPolicyProvider())
    policy_index.register(CleanupPolicyProvider())
    policy_index.register(
        CombinedPolicyProvider(
            verbose=verbose,
        )
    )
    policy_index.register(
        CompiledPolicyProvider(
            verbose=verbose,
        )
    )
    policy_index.register(
        BinaryCompiledPolicyProvider(
            verbose=verbose,
        )
    )
    policy_index.register(
        MacroMatchPolicyProvider(
            verbose=verbose,
        )
    )
    policy_index.register(
        MacroReplacePolicyProvider(
            verbose=verbose,
        )
    )
    policy_index.register(
        GatherSourceTextPolicyProvider(
            verbose=verbose,
        )
    )
    policy_index.register(
        ExpandedGuardPolicyProvider(
            verbose=verbose,
        )
    )

    shutil.rmtree(output_dir, ignore_errors=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    for policy_type in get_policy_types():
        if policy_type.output is None:
            continue

        policy = policy_index.find(policy_type)
        if not policy:
            continue

        process_policy_output(
            policy,
            output_dir,
        )


if __name__ == '__main__':
    decompile_cil()

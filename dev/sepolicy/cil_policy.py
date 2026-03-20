# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from itertools import chain
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from sepolicy.cil_rule import CilRule
from sepolicy.conditional_type import ConditionalType
from sepolicy.contexts import (
    ContextsType,
    find_contexts_used_types,
    parse_contexts_texts,
    resolve_contexts_paths,
    split_contexts_text,
)
from sepolicy.match import find_used_types, merge_ioctl_rules
from sepolicy.policy_info import PolicyInfo
from sepolicy.rule import Rule


def decompile_one_cil(
    cil_path: Path,
    name: str,
    conditional_types_map: Optional[Dict[str, ConditionalType]] = None,
    missing_generated_types: Optional[Set[str]] = None,
    used_types: Optional[Set[str]] = None,
    version: Optional[str] = None,
):
    if conditional_types_map is None:
        conditional_types_map = {}

    if missing_generated_types is None:
        missing_generated_types = set()

    if used_types is None:
        used_types = set()

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


@dataclass
class PrebuiltPolicy:
    rules: List[Rule]
    genfs_rules: List[Rule]
    contexts: Dict[ContextsType, List[Tuple[str, ...]]]
    extra_rules: List[Tuple[str, List[Rule]]]
    used_types: Set[str]


def parse_prebuilt(policy_info: PolicyInfo, verbose: bool):
    conditional_types_map: Dict[str, ConditionalType] = {}
    missing_generated_types: Set[str] = set()
    extra_rules: List[Tuple[str, List[Rule]]] = []
    used_types: Set[str] = set()

    rules, genfs_rules = decompile_one_cil(
        policy_info.policy_path,
        conditional_types_map=conditional_types_map,
        missing_generated_types=missing_generated_types,
        used_types=used_types,
        version=policy_info.version,
        name='decompiled policy',
    )

    # Load generated types and rules from platform policy
    # Add platform rules and remove them later to allow matching
    # set_prop(vendor_init, ...)
    # Since somehow allow vendor_init property_socket:sock_file write;
    # only ends up in platform sepolicy
    if policy_info.platform_policy_path is not None:
        platform_rules, _ = decompile_one_cil(
            policy_info.platform_policy_path,
            conditional_types_map=conditional_types_map,
            missing_generated_types=set(),
            used_types=set(),
            version=policy_info.version,
            name='platform policy',
        )
        extra_rules.append(('platform policy', platform_rules))

    contexts_file_paths = resolve_contexts_paths(
        [policy_info.path],
        policy_info.partition_name,
        None,
        verbose,
    )
    contexts_texts = split_contexts_text(
        contexts_file_paths,
    )
    contexts, _ = parse_contexts_texts(
        contexts_texts,
    )

    # Find all used types
    find_used_types(rules, used_types)
    find_used_types(genfs_rules, used_types)
    find_contexts_used_types(contexts, used_types)

    return PrebuiltPolicy(
        rules=rules,
        genfs_rules=genfs_rules,
        contexts=contexts,
        extra_rules=extra_rules,
        used_types=used_types,
    )

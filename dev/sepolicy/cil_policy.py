# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from sepolicy.cil_rule import CilRule
from sepolicy.conditional_type import ConditionalType
from sepolicy.contexts import (
    ContextsType,
    find_contexts_used_types,
    parse_contexts_texts,
    split_contexts_text,
)
from sepolicy.match import find_public_rules, find_used_types, merge_ioctl_rules
from sepolicy.policy_info import PolicyInfo
from sepolicy.rule import RULE_DYNAMIC_PARTS_INDEX, Rule
from utils.mld import MultiLevelDict


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
    rules: List[Rule] = []

    def add_rule(rule: Rule):
        rules.append(rule)

    def add_genfs_rule(rule: Rule):
        genfs_rules.append(rule)

    for cil_line in cil_lines:
        CilRule.from_line(
            cil_line,
            conditional_types_map=conditional_types_map,
            missing_generated_types=missing_generated_types,
            add_rule=add_rule,
            add_genfs_rule=add_genfs_rule,
            version=version,
        )

    # ioctl rules are split at comments / newlines by the compiler
    # merge adjacent ioctl rules of the same type back
    # TODO: this won't work if the rules end up next to eachother but
    # they weren't next to eachother initially, but the chances for that
    # are very low
    rules = merge_ioctl_rules(rules, name)

    return rules, genfs_rules


@dataclass
class PrebuiltPolicy:
    mld: MultiLevelDict[Rule]
    public_mld: MultiLevelDict[Rule]
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
    for policy_version, policy_path in policy_info.extra_rules_paths:
        platform_rules, _ = decompile_one_cil(
            policy_path,
            conditional_types_map=conditional_types_map,
            missing_generated_types=set(),
            used_types=set(),
            version=policy_version,
            name='platform policy',
        )
        extra_rules.append(('platform policy', platform_rules))

    contexts_texts = split_contexts_text(
        policy_info.contexts_file_paths,
    )
    contexts, _ = parse_contexts_texts(
        contexts_texts,
    )

    # Find all used types
    find_used_types(rules, used_types)
    find_used_types(genfs_rules, used_types)
    find_contexts_used_types(contexts, used_types)

    # Generate match dicts starting after the first token of the rule
    # which is almost always the type
    # This means that we can't match rules not knowing their type, but
    # that's fine usually
    mld: MultiLevelDict[Rule] = MultiLevelDict(RULE_DYNAMIC_PARTS_INDEX)
    mld.add_many(rules, lambda r: r.hash_values)

    public_rules: List[Rule] = []
    for policy_version, policy_path in policy_info.public_rules_paths:
        # Load rules being referenced by other sepolicy which need to be
        # public
        referencing_rules, _ = decompile_one_cil(
            policy_path,
            name='referencing policy',
            version=policy_version,
        )

        public_rules += find_public_rules(mld, referencing_rules)

    # Add all public rules into a separate dictionary to be able to group them
    # and do the same processing as private rules
    public_mld = MultiLevelDict[Rule](RULE_DYNAMIC_PARTS_INDEX)
    public_mld.add_many(public_rules, lambda r: r.hash_values)

    return PrebuiltPolicy(
        mld=mld,
        public_mld=public_mld,
        genfs_rules=genfs_rules,
        contexts=contexts,
        extra_rules=extra_rules,
        used_types=used_types,
    )

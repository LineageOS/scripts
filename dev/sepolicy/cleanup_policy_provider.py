# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Optional

from sepolicy.contexts import remove_source_contexts
from sepolicy.expander import EXPAND_TYPES, Coverage
from sepolicy.policy import (
    PolicyCleanupOrigin,
    PolicyIndex,
    PolicyMetadata,
    PolicyProvider,
    PolicyType,
)
from sepolicy.rule_container import RuleContainer


def remove_covered_rules(rules: RuleContainer, covering: RuleContainer):
    coverage = Coverage(covering)
    result = RuleContainer()

    for rule in rules:
        if rule in covering:
            continue

        if (
            rule.rule_type in EXPAND_TYPES
            and coverage.uncovered(rule).is_empty()
        ):
            continue

        result.add(rule, rules.marks(rule))

    return result


class CleanupPolicyProvider(PolicyProvider):
    def __init__(self):
        super().__init__(
            policy_origin=PolicyCleanupOrigin,
        )

    def resolve_metadata(
        self,
        policy_index: PolicyIndex,
        policy_type: PolicyType,
        requested: Optional[PolicyMetadata],
    ):
        assert isinstance(policy_type.origin, PolicyCleanupOrigin)

        return policy_index.resolve_metadata(
            policy_type.origin.source,
            requested,
        )

    def get_policy(
        self,
        policy_index: PolicyIndex,
        policy_type: PolicyType,
        metadata: Optional[PolicyMetadata],
    ):
        assert isinstance(policy_type.origin, PolicyCleanupOrigin)

        source_policy = policy_index.find(
            policy_type.origin.source,
            metadata,
        )
        if source_policy is None:
            return None

        rules = source_policy.rules
        genfs_rules = source_policy.genfs_rules
        contexts = source_policy.contexts

        for removed_policy_type in policy_type.origin.removed:
            cleanup_policy = policy_index.get(
                removed_policy_type,
                source_policy.metadata,
            )

            rules = rules - cleanup_policy.rules
            genfs_rules = genfs_rules - cleanup_policy.genfs_rules
            contexts, _ = remove_source_contexts(
                contexts,
                cleanup_policy.contexts,
            )

        for covered_policy_type in policy_type.origin.covered:
            covered_policy = policy_index.get(
                covered_policy_type,
                source_policy.metadata,
            )
            rules = remove_covered_rules(rules, covered_policy.rules)
            genfs_rules = genfs_rules - covered_policy.genfs_rules
            contexts, _ = remove_source_contexts(
                contexts,
                covered_policy.contexts,
            )

        return source_policy.copy(
            policy_type=policy_type,
            rules=rules,
            genfs_rules=genfs_rules,
            contexts=contexts,
        )

# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Dict, Optional

from sepolicy.policy import (
    PolicyAddOrigin,
    PolicyIndex,
    PolicyMetadata,
    PolicyProvider,
    PolicyType,
)
from sepolicy.rule import Rule
from sepolicy.rule_container import RuleContainer


class AddPolicyProvider(PolicyProvider):
    def __init__(self):
        super().__init__(PolicyAddOrigin)

    def resolve_metadata(
        self,
        policy_index: PolicyIndex,
        policy_type: PolicyType,
        requested: Optional[PolicyMetadata],
    ):
        assert isinstance(policy_type.origin, PolicyAddOrigin)

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
        assert isinstance(policy_type.origin, PolicyAddOrigin)
        origin = policy_type.origin

        source_policy = policy_index.find(origin.source, metadata)
        if source_policy is None:
            return None

        added_policy = policy_index.find(origin.added)
        if added_policy is None:
            return source_policy.copy(
                policy_type=policy_type,
                rules=source_policy.rules,
                genfs_rules=source_policy.genfs_rules,
                contexts=source_policy.contexts,
            )

        rules = RuleContainer(source_policy.rules)
        rules.add_many(added_policy.rules)

        genfs_rules = RuleContainer(source_policy.genfs_rules)
        genfs_rules.add_many(added_policy.genfs_rules)

        guarded_rules: Dict[Rule, str] = dict(source_policy.guarded_rules or {})
        for rule in added_policy.rules:
            guarded_rules[rule] = origin.guard

        new_policy = source_policy.copy(
            policy_type=policy_type,
            rules=rules,
            genfs_rules=genfs_rules,
            contexts=source_policy.contexts,
        )
        new_policy.guarded_rules = guarded_rules
        return new_policy

# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Optional

from sepolicy.policy import (
    PolicyIndex,
    PolicyMetadata,
    PolicyProvider,
    PolicyReferencedOrigin,
    PolicyType,
)
from sepolicy.rule_container import RuleContainer


class ReferencedPolicyProvider(PolicyProvider):
    def __init__(self):
        super().__init__(PolicyReferencedOrigin)

    def resolve_metadata(
        self,
        policy_index: PolicyIndex,
        policy_type: PolicyType,
        requested: Optional[PolicyMetadata],
    ):
        assert isinstance(policy_type.origin, PolicyReferencedOrigin)

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
        assert isinstance(policy_type.origin, PolicyReferencedOrigin)

        source_policy = policy_index.find(policy_type.origin.source)
        if source_policy is None:
            return None

        reference_policy = policy_index.get(policy_type.origin.reference)

        assert not reference_policy.contexts, reference_policy.contexts
        assert not reference_policy.genfs_rules, reference_policy.genfs_rules

        if policy_type.origin.in_or_out:
            rules = source_policy.rules & reference_policy.rules
            genfs_rules = RuleContainer()
            contexts = {}
        else:
            rules = source_policy.rules - reference_policy.rules
            genfs_rules = source_policy.genfs_rules
            contexts = source_policy.contexts

        return source_policy.copy(
            policy_type=policy_type,
            rules=rules,
            genfs_rules=genfs_rules,
            contexts=contexts,
        )

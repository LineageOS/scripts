# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Optional

from sepolicy.match import discard_rule_matches, match_macros_rules
from sepolicy.policy import (
    PolicyIndex,
    PolicyMacroMatchOrigin,
    PolicyMetadata,
    PolicyProvider,
    PolicyType,
)


class MacroMatchPolicyProvider(PolicyProvider):
    def __init__(self, verbose: bool):
        super().__init__(PolicyMacroMatchOrigin)

        self.__verbose = verbose

    def resolve_metadata(
        self,
        policy_index: PolicyIndex,
        policy_type: PolicyType,
        requested: Optional[PolicyMetadata],
    ):
        assert isinstance(policy_type.origin, PolicyMacroMatchOrigin)

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
        assert isinstance(policy_type.origin, PolicyMacroMatchOrigin)

        source_policy = policy_index.find(
            policy_type.origin.source,
            metadata,
        )
        if source_policy is None:
            return None

        macros_policy = policy_index.get(
            policy_type.origin.macros,
            source_policy.metadata,
        )
        assert macros_policy.macros is not None
        macros = macros_policy.macros

        rule_matches = match_macros_rules(
            source_policy.rules,
            macros.macros_name_rules,
            self.__verbose,
        )
        rule_matches = discard_rule_matches(rule_matches, self.__verbose)

        policy = source_policy.copy(
            policy_type=policy_type,
            rules=source_policy.rules,
            genfs_rules=source_policy.genfs_rules,
            contexts=source_policy.contexts,
        )
        policy.rule_matches = rule_matches
        policy.macros = macros
        return policy

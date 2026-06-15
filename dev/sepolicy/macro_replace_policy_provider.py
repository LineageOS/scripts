# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Optional

from sepolicy.match import replace_macro_rules
from sepolicy.policy import (
    PolicyIndex,
    PolicyMacroReplaceOrigin,
    PolicyMetadata,
    PolicyProvider,
    PolicyType,
)
from sepolicy.rule_container import RuleContainer


class MacroReplacePolicyProvider(PolicyProvider):
    def __init__(self, verbose: bool):
        super().__init__(PolicyMacroReplaceOrigin)

        self.__verbose = verbose

    def resolve_metadata(
        self,
        policy_index: PolicyIndex,
        policy_type: PolicyType,
        requested: Optional[PolicyMetadata],
    ):
        assert isinstance(policy_type.origin, PolicyMacroReplaceOrigin)

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
        assert isinstance(policy_type.origin, PolicyMacroReplaceOrigin)

        source_policy = policy_index.find(
            policy_type.origin.source,
            metadata,
        )
        if source_policy is None:
            return None

        assert source_policy.rule_matches is not None

        rules = RuleContainer(source_policy.rules)

        replace_macro_rules(
            rules,
            source_policy.rule_matches,
            source_policy.pretty_name,
            self.__verbose,
        )

        return source_policy.copy(
            policy_type=policy_type,
            rules=rules,
            genfs_rules=source_policy.genfs_rules,
            contexts=source_policy.contexts,
        )

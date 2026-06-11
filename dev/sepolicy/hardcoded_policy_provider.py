# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Optional

from sepolicy.policy import (
    Policy,
    PolicyHardcodedOrigin,
    PolicyIndex,
    PolicyMetadata,
    PolicyProvider,
    PolicyType,
)
from sepolicy.rule_container import RuleContainer


class HardcodedPolicyProvider(PolicyProvider):
    def __init__(self):
        super().__init__(PolicyHardcodedOrigin)

    def resolve_metadata(
        self,
        policy_index: PolicyIndex,
        policy_type: PolicyType,
        requested: Optional[PolicyMetadata],
    ):
        return None

    def get_policy(
        self,
        policy_index: PolicyIndex,
        policy_type: PolicyType,
        metadata: Optional[PolicyMetadata],
    ):
        assert isinstance(policy_type.origin, PolicyHardcodedOrigin)

        return Policy(
            type=policy_type,
            rules=RuleContainer(policy_type.origin.rules),
            genfs_rules=RuleContainer(),
            contexts={},
            metadata=None,
        )

# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from sepolicy.cil_policy import parse_cil_lines
from sepolicy.classmap import Classmap
from sepolicy.conditional_type import ConditionalType
from sepolicy.policy import (
    Policy,
    PolicyIndex,
    PolicyMetadata,
    PolicyProvider,
    PolicySourceCilOrigin,
    PolicyType,
)
from sepolicy.rule_container import RuleContainer
from sepolicy.source_policy import get_source_policy_path


class SourceCilPolicyProvider(PolicyProvider):
    def __init__(
        self,
        current: bool,
        verbose: bool,
    ):
        super().__init__(PolicySourceCilOrigin)

        self.__current = current
        self.__verbose = verbose

    def get_policy(
        self,
        policy_index: PolicyIndex,
        policy_type: PolicyType,
        metadata: Optional[PolicyMetadata] = None,
    ):
        assert metadata is not None

        assert isinstance(policy_type.origin, PolicySourceCilOrigin)

        sepolicy_path = get_source_policy_path(
            metadata.version,
            self.__current,
        )

        source_cil_rules_path = Path(
            sepolicy_path,
            policy_type.origin.cil_file_name,
        )

        genfs_rules = RuleContainer()
        rules = RuleContainer()
        conditional_types_map: Dict[str, ConditionalType] = {}

        parse_cil_lines(
            source_cil_rules_path,
            rules,
            genfs_rules,
            conditional_types_map,
            reference_conditional_types_maps=[],
            # TODO
            # Currently this is only used for technical_debt.cil which does not
            # need classmap
            # We only pass it here to prevent parse_cil_lines() from parsing it
            classmap=Classmap({}),
            version=metadata.version,
            name=policy_type.pretty_name,
            verbose=self.__verbose,
        )

        return Policy(
            policy_type,
            rules,
            genfs_rules=genfs_rules,
            contexts={},
            conditional_types_map=conditional_types_map,
            metadata=metadata,
        )

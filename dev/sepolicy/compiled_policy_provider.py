# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Dict, Optional

from sepolicy.cil_policy import parse_cil_lines
from sepolicy.compile_utils import source_to_cil_policy
from sepolicy.conditional_type import ConditionalType
from sepolicy.policy import (
    Policy,
    PolicyCompiledOrigin,
    PolicyIndex,
    PolicyMetadata,
    PolicyProvider,
    PolicyType,
)
from sepolicy.rule_container import RuleContainer


class CompiledPolicyProvider(PolicyProvider):
    def __init__(self, verbose: bool):
        super().__init__(
            policy_origin=PolicyCompiledOrigin,
        )

        self.__verbose = verbose

    def get_policy(
        self,
        policy_index: PolicyIndex,
        policy_type: PolicyType,
        metadata: Optional[PolicyMetadata],
    ):
        assert isinstance(policy_type.origin, PolicyCompiledOrigin)
        assert metadata is not None

        combined_policy = policy_index.get(policy_type.origin.source, metadata)
        assert combined_policy.text is not None

        genfs_rules = RuleContainer()
        rules = RuleContainer()
        conditional_types_map: Dict[str, ConditionalType] = {}

        with NamedTemporaryFile(mode='w') as source_file:
            source_file.write(combined_policy.text)
            source_file.flush()
            source_path = Path(source_file.name)

            with source_to_cil_policy(source_path) as cil_policy_path:
                cil_text = cil_policy_path.read_text()

                parse_cil_lines(
                    cil_policy_path,
                    rules,
                    genfs_rules,
                    conditional_types_map,
                    reference_conditional_types_maps=[],
                    classmap=None,
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
            text=cil_text,
        )

# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path
from typing import (
    Optional,
)

from sepolicy.cil_policy import (
    get_dump_policy_version,
    parse_dump_policy_contexts,
    parse_dump_policy_rules,
    parse_dump_policy_variables,
)
from sepolicy.policy import (
    Policy,
    PolicyDumpCilOrigin,
    PolicyIndex,
    PolicyMetadata,
    PolicyProvider,
    PolicyType,
)


class DumpCilPolicyProvider(PolicyProvider):
    def __init__(
        self,
        dump_root: Path,
        verbose: bool,
    ):
        super().__init__(
            policy_origin=PolicyDumpCilOrigin,
        )

        self.__dump_root = dump_root
        self.__verbose = verbose

    def resolve_metadata(
        self,
        policy_index: PolicyIndex,
        policy_type: PolicyType,
        requested: Optional[PolicyMetadata],
    ):
        assert isinstance(policy_type.origin, PolicyDumpCilOrigin)

        version = get_dump_policy_version(
            self.__dump_root,
            policy_type.origin.version_source,
        )

        variables = parse_dump_policy_variables(
            self.__dump_root,
            version=version,
            recovery=policy_type.origin.partition == 'recovery',
        )

        return PolicyMetadata(version, variables)

    def get_policy(
        self,
        policy_index: PolicyIndex,
        policy_type: PolicyType,
        metadata: Optional[PolicyMetadata],
    ):
        assert isinstance(policy_type.origin, PolicyDumpCilOrigin)
        assert metadata is not None

        partition = policy_type.origin.partition

        parse_result = parse_dump_policy_rules(
            policy_index,
            self.__dump_root,
            policy_type,
            metadata=metadata,
            verbose=self.__verbose,
        )
        if parse_result is None:
            return None

        (
            rules,
            classmap,
            genfs_rules,
            conditional_types_map,
        ) = parse_result

        assert policy_type.origin.contexts_name_map is not None
        contexts = parse_dump_policy_contexts(
            self.__dump_root,
            partition=partition,
            contexts_name_map=policy_type.origin.contexts_name_map,
            name=policy_type.pretty_name,
            verbose=self.__verbose,
        )

        return Policy(
            policy_type,
            rules,
            genfs_rules,
            contexts,
            conditional_types_map=conditional_types_map,
            metadata=metadata,
            classmap=classmap,
        )

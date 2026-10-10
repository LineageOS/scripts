# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path
from typing import Optional

from sepolicy.cil_policy import (
    decompile_binary_to_policy,
    get_dump_policy_metadata,
)
from sepolicy.policy import (
    PolicyDumpBinaryOrigin,
    PolicyIndex,
    PolicyMetadata,
    PolicyProvider,
    PolicyType,
)


class DumpBinaryPolicyProvider(PolicyProvider):
    def __init__(
        self,
        dump_root: Path,
        verbose: bool,
    ):
        super().__init__(PolicyDumpBinaryOrigin)

        self.__dump_root = dump_root
        self.__verbose = verbose

    def resolve_metadata(
        self,
        policy_index: PolicyIndex,
        policy_type: PolicyType,
        requested: Optional[PolicyMetadata],
    ):
        assert isinstance(policy_type.origin, PolicyDumpBinaryOrigin)

        return get_dump_policy_metadata(
            self.__dump_root,
            policy_type.origin.version_source,
            recovery=policy_type.origin.recovery,
        )

    def get_policy(
        self,
        policy_index: PolicyIndex,
        policy_type: PolicyType,
        metadata: Optional[PolicyMetadata],
    ):
        assert isinstance(policy_type.origin, PolicyDumpBinaryOrigin)
        assert metadata is not None

        binary_policy_path = Path(
            self.__dump_root,
            policy_type.origin.file_name,
        )
        if not binary_policy_path.exists():
            return None

        return decompile_binary_to_policy(
            binary_policy_path,
            policy_type,
            metadata,
            self.__verbose,
        )

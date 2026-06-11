# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Optional

from sepolicy.cil_policy import decompile_binary_to_policy
from sepolicy.compile_utils import cil_to_binary_policy
from sepolicy.policy import (
    PolicyBinaryCompiledOrigin,
    PolicyIndex,
    PolicyMetadata,
    PolicyProvider,
    PolicyType,
)


class BinaryCompiledPolicyProvider(PolicyProvider):
    def __init__(self, verbose: bool):
        super().__init__(
            policy_origin=PolicyBinaryCompiledOrigin,
        )

        self.__verbose = verbose

    def get_policy(
        self,
        policy_index: PolicyIndex,
        policy_type: PolicyType,
        metadata: Optional[PolicyMetadata],
    ):
        assert isinstance(policy_type.origin, PolicyBinaryCompiledOrigin)
        assert metadata is not None

        compiled_policy = policy_index.get(policy_type.origin.source, metadata)
        assert compiled_policy.text is not None

        with NamedTemporaryFile(mode='w') as cil_file:
            cil_file.write(compiled_policy.text)
            cil_file.flush()
            cil_path = Path(cil_file.name)

            with cil_to_binary_policy(cil_path) as binary_policy_path:
                return decompile_binary_to_policy(
                    binary_policy_path,
                    policy_type,
                    metadata,
                    self.__verbose,
                )

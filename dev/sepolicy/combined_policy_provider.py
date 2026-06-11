# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Optional, Set, Tuple

from sepolicy.expand import expand_macro_calls
from sepolicy.policy import (
    Policy,
    PolicyCombinedOrigin,
    PolicyIndex,
    PolicyMetadata,
    PolicyProvider,
    PolicyType,
)
from sepolicy.rule_container import RuleContainer
from sepolicy.source_text import PolicyFileType, SourceText


def _merge_sources(
    policy_index: PolicyIndex,
    source_text: SourceText,
    sources: Optional[Tuple[PolicyType, ...]],
    metadata: PolicyMetadata,
    allowed_types: Optional[Set[PolicyFileType]] = None,
    disallowed_types: Optional[Set[PolicyFileType]] = None,
):
    if sources is None:
        return

    for policy_type in sources:
        policy = policy_index.get(policy_type, metadata)
        assert policy.source_text is not None

        source_text.update(
            policy.source_text,
            allowed_types=allowed_types,
            disallowed_types=disallowed_types,
        )


def combine_and_expand_sources(
    policy_index: PolicyIndex,
    macro_sources: Optional[Tuple[PolicyType, ...]],
    rule_sources: Optional[Tuple[PolicyType, ...]],
    metadata: PolicyMetadata,
    verbose: bool,
    attribute_sources: Optional[Tuple[PolicyType, ...]] = None,
) -> str:
    source_text = SourceText()

    _merge_sources(
        policy_index,
        source_text,
        macro_sources,
        metadata,
        disallowed_types={PolicyFileType.TE},
    )
    _merge_sources(
        policy_index,
        source_text,
        attribute_sources,
        metadata,
        allowed_types={PolicyFileType.ATTRIBUTES},
    )
    _merge_sources(
        policy_index,
        source_text,
        rule_sources,
        metadata,
        allowed_types={PolicyFileType.TE},
    )

    return expand_macro_calls(
        texts=[],
        environment_texts=source_text.get_texts(),
        variables=metadata.variables,
        preserve_macros=False,
        text_name='expanded_rules',
        verbose=verbose,
    )


class CombinedPolicyProvider(PolicyProvider):
    def __init__(self, verbose: bool):
        super().__init__(
            policy_origin=PolicyCombinedOrigin,
        )

        self.__verbose = verbose

    def get_policy(
        self,
        policy_index: PolicyIndex,
        policy_type: PolicyType,
        metadata: Optional[PolicyMetadata],
    ):
        assert isinstance(policy_type.origin, PolicyCombinedOrigin)
        assert metadata is not None

        expanded_rules = combine_and_expand_sources(
            policy_index,
            policy_type.origin.macro_sources,
            policy_type.origin.rule_sources,
            metadata,
            self.__verbose,
            attribute_sources=policy_type.origin.attribute_sources,
        )

        return Policy(
            policy_type,
            RuleContainer(),
            genfs_rules=RuleContainer(),
            contexts={},
            metadata=metadata,
            text=expanded_rules,
        )

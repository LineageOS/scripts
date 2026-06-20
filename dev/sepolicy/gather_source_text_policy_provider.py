# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path
from typing import Optional

from sepolicy.output import group_rules, render_grouped_rules
from sepolicy.policy import (
    Policy,
    PolicyGatherSourceTextOrigin,
    PolicyIndex,
    PolicyMetadata,
    PolicyProvider,
    PolicyType,
)
from sepolicy.rule_container import RuleContainer
from sepolicy.source_text import (
    POLICY_ORDER_MAP,
    PolicyFileType,
    SourceText,
)


class GatherSourceTextPolicyProvider(PolicyProvider):
    def __init__(self, verbose: bool):
        super().__init__(PolicyGatherSourceTextOrigin)

        self.__verbose = verbose

    def resolve_metadata(
        self,
        policy_index: PolicyIndex,
        policy_type: PolicyType,
        requested: Optional[PolicyMetadata],
    ):
        assert isinstance(policy_type.origin, PolicyGatherSourceTextOrigin)

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
        assert isinstance(policy_type.origin, PolicyGatherSourceTextOrigin)

        source_policy = policy_index.find(
            policy_type.origin.source,
            metadata,
        )
        if source_policy is None:
            return None

        grouped_rules = group_rules(source_policy.rules)
        rendered = render_grouped_rules(
            grouped_rules,
            source_policy.macros,
            rule_guard=source_policy.guarded_rules,
            mark_source=source_policy.rules,
        )

        source_text = SourceText()
        name_prefix = Path(policy_type.name)
        for name, text in rendered.items():
            path = name_prefix / name
            if name.endswith('.te'):
                file_type = PolicyFileType.TE
            else:
                file_type = POLICY_ORDER_MAP.get(
                    Path(name).stem,
                    PolicyFileType.TE,
                )
            source_text.texts[path] = text
            source_text.paths[file_type].append(path)

        return Policy(
            policy_type,
            RuleContainer(),
            genfs_rules=source_policy.genfs_rules,
            contexts=source_policy.contexts,
            metadata=source_policy.metadata,
            source_text=source_text,
        )

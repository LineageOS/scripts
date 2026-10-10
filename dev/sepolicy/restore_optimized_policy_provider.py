# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from sepolicy.expander import Coverage
from sepolicy.policy import (
    PolicyIndex,
    PolicyMetadata,
    PolicyProvider,
    PolicyRestoreOptimizedOrigin,
    PolicyType,
)
from sepolicy.rule import Rule, RuleType
from sepolicy.rule_container import RuleContainer
from sepolicy.varargs import Perms

RESTORED_TYPES = frozenset(
    {
        RuleType.ALLOW,
        RuleType.AUDITALLOW,
        RuleType.DONTAUDIT,
    }
)


def restore_optimized_rule(
    rule: Rule,
    coverage: Coverage,
    class_perms: Dict[str, List[Tuple[str, Set[str]]]],
) -> Rule:
    if rule.rule_type not in RESTORED_TYPES:
        return rule

    class_name = rule.parts[2]
    if not isinstance(class_name, str) or class_name not in class_perms:
        return rule

    assert isinstance(rule.varargs, Perms)

    candidates = sorted(class_perms[class_name], key=lambda np: len(np[1]))
    for _, perms in candidates:
        restored = Perms(perms, False)
        if not rule.varargs <= restored:
            continue

        if restored <= rule.varargs:
            return rule

        restored_rule = Rule(rule.rule_type, rule.parts, restored)
        if coverage.uncovered(restored_rule).is_empty():
            return restored_rule

    return rule


class RestoreOptimizedPolicyProvider(PolicyProvider):
    def __init__(self):
        super().__init__(PolicyRestoreOptimizedOrigin)

    def get_policy(
        self,
        policy_index: PolicyIndex,
        policy_type: PolicyType,
        metadata: Optional[PolicyMetadata],
    ):
        assert isinstance(policy_type.origin, PolicyRestoreOptimizedOrigin)
        origin = policy_type.origin

        source_policy = policy_index.find(origin.source, metadata)
        if source_policy is None:
            return None

        macros_policy = policy_index.get(
            origin.macros,
            source_policy.metadata,
        )
        assert macros_policy.macros is not None
        class_perms = macros_policy.macros.class_perms

        reference_policy = policy_index.get(
            origin.reference,
            source_policy.metadata,
        )
        coverage = Coverage(reference_policy.rules)

        rules = RuleContainer()
        for rule in source_policy.rules:
            restored = restore_optimized_rule(rule, coverage, class_perms)
            rules.add(restored, source_policy.rules.marks(rule))

        return source_policy.copy(
            policy_type=policy_type,
            rules=rules,
            genfs_rules=source_policy.genfs_rules,
            contexts=source_policy.contexts,
        )

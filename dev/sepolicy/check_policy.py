# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

# Verifies the decompiled output by diffing the reconstructed policies (which
# policy.py recompiles the way the build does) against the prebuilt policy they
# were reconstructed from: the platform/system_ext/product/vendor cils against
# the prebuilt partition cils, and the whole reconstruction binary against the
# prebuilt recovery binary.

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Tuple

from sepolicy.policy import (
    PolicyIndex,
    PolicyType,
    platform,
    product,
    reconstructed_platform,
    reconstructed_product,
    reconstructed_recovery,
    reconstructed_system_ext,
    reconstructed_vendor,
    recovery,
    source_platform_technical_debt,
    system_ext,
    vendor,
)
from sepolicy.rule import RuleType
from sepolicy.rule_container import RuleContainer
from utils.utils import Color, color_print


@dataclass(frozen=True)
class PartitionCheck:
    label: str
    reconstructed: PolicyType
    prebuilt: PolicyType
    dependencies: Tuple[PolicyType, ...]


PARTITION_CHECKS = [
    PartitionCheck(
        label='platform',
        reconstructed=reconstructed_platform,
        prebuilt=platform,
        dependencies=(),
    ),
    PartitionCheck(
        label='system_ext',
        reconstructed=reconstructed_system_ext,
        prebuilt=system_ext,
        dependencies=(platform,),
    ),
    PartitionCheck(
        label='product',
        reconstructed=reconstructed_product,
        prebuilt=product,
        dependencies=(platform, system_ext),
    ),
    PartitionCheck(
        label='vendor',
        reconstructed=reconstructed_vendor,
        prebuilt=vendor,
        dependencies=(platform, system_ext, product),
    ),
]


def _union(containers: Sequence[RuleContainer]) -> RuleContainer:
    out = RuleContainer()
    for container in containers:
        for rule in container:
            out.add(rule)
    return out


def _drop_versioned_types(
    prebuilt: RuleContainer,
    reconstructed: RuleContainer,
) -> RuleContainer:
    types = {
        rule.parts[0]
        for rule in reconstructed
        if rule.rule_type == RuleType.TYPE
    }
    versioned = {
        rule.parts[0]
        for rule in prebuilt
        if rule.rule_type == RuleType.EXPANDATTRIBUTE
        and rule.parts[1] == 'true'
        and rule.parts[0] in types
    }

    out = RuleContainer()
    for rule in prebuilt:
        rule_type = rule.rule_type
        if rule_type == RuleType.EXPANDATTRIBUTE and rule.parts[0] in versioned:
            continue
        if rule_type == RuleType.ATTRIBUTE and rule.parts[0] in versioned:
            continue
        if rule_type == RuleType.TYPEATTRIBUTE and rule.parts[1] in versioned:
            continue
        out.add(rule)
    return out


def _report(
    name: str,
    reconstructed: RuleContainer,
    prebuilt: RuleContainer,
) -> bool:
    added = reconstructed - prebuilt
    missing = prebuilt - reconstructed

    if not added and not missing:
        return True

    color_print(name, color=Color.RED)
    for rule in sorted(added, key=str):
        color_print(f'  + {rule}', color=Color.RED)
    for rule in sorted(missing, key=str):
        color_print(f'  - {rule}', color=Color.RED)
    return False


def _check_recovery(policy_index: PolicyIndex) -> bool:
    recovery_policy = policy_index.find(recovery)
    if recovery_policy is None:
        return True

    reconstructed_policy = policy_index.get(
        reconstructed_recovery,
        recovery_policy.metadata,
    )
    return _report(
        'recovery',
        reconstructed_policy.rules,
        recovery_policy.rules,
    )


def run_checks(policy_index: PolicyIndex) -> bool:
    color_print(
        'Checking partitions against prebuilt variants...',
        color=Color.YELLOW,
    )

    all_passed = True

    for check in PARTITION_CHECKS:
        prebuilt_policy = policy_index.get(check.prebuilt)
        metadata = prebuilt_policy.metadata
        dependency_policies = [
            policy_index.get(dependency) for dependency in check.dependencies
        ]
        prebuilt = _union(
            tuple(dependency.rules for dependency in dependency_policies)
            + (prebuilt_policy.rules,)
        )

        reconstructed_policy = policy_index.get(
            check.reconstructed,
            metadata,
        )
        technical_debt_policy = policy_index.get(
            source_platform_technical_debt,
            metadata,
        )
        reconstructed = _union(
            (
                reconstructed_policy.rules,
                technical_debt_policy.rules,
            )
        )

        expected = prebuilt
        if check.label == 'vendor':
            expected = _drop_versioned_types(prebuilt, reconstructed)

        all_passed &= _report(check.label, reconstructed, expected)

    all_passed &= _check_recovery(policy_index)

    if all_passed:
        color_print(
            'All partitions match their prebuilt variants',
            color=Color.GREEN,
        )
    else:
        color_print(
            'Some partitions do not match their prebuilt variants',
            color=Color.RED,
        )

    return all_passed

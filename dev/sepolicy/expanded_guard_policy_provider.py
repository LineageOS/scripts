# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from enum import Enum, auto
from typing import Dict, List, Optional, Set, Tuple

from sepolicy.expander import (
    EXPAND_TYPES,
    Resolver,
    str_part,
    varargs_subset,
)
from sepolicy.policy import (
    PolicyExpandedGuardOrigin,
    PolicyIndex,
    PolicyMetadata,
    PolicyProvider,
    PolicyType,
)
from sepolicy.rule import Rule, RuleType
from sepolicy.rule_container import RuleContainer
from sepolicy.varargs import Ioctls, Perms
from utils.utils import Color, color_print


class GuardStatus(Enum):
    ALL_PRESENT = auto()
    ALL_ABSENT = auto()
    MIXED = auto()
    EMPTY = auto()


def is_expansion_present(
    expanded: Rule,
    rules: RuleContainer,
) -> bool:
    assert isinstance(expanded.varargs, (Perms, Ioctls))
    match_keys = (expanded.rule_type, *expanded.parts, None)
    return any(
        varargs_subset(expanded.varargs, match.varargs)
        for match in rules.match(match_keys)
        if isinstance(match.varargs, (Perms, Ioctls))
    )


def get_membership_pairs(
    rule: Rule,
    expanded: Rule,
    resolver: Resolver,
) -> List[Tuple[str, str]]:
    pairs: List[Tuple[str, str]] = []
    src, dst = rule.parts[0], rule.parts[1]
    expanded_src, expanded_dst = expanded.parts[0], expanded.parts[1]
    if (
        isinstance(src, str)
        and isinstance(expanded_src, str)
        and expanded_src != src
        and resolver.is_attribute(src)
    ):
        pairs.append((src, expanded_src))

    if (
        isinstance(dst, str)
        and isinstance(expanded_dst, str)
        and expanded_dst not in (dst, 'self')
        and resolver.is_attribute(dst)
    ):
        pairs.append((dst, expanded_dst))

    return pairs


def get_absent_memberships(
    source_rules: RuleContainer,
    absent_memberships: Set[Tuple[str, str]],
) -> List[Rule]:
    absent: List[Rule] = []
    for rule in source_rules:
        if rule.rule_type != RuleType.TYPEATTRIBUTE:
            continue
        member = str_part(rule, 0)
        attribute = str_part(rule, 1)
        if (attribute, member) in absent_memberships:
            absent.append(rule)
    return absent


def classify_rules(
    expandable: List[Rule],
    resolver: Resolver,
    rules: RuleContainer,
) -> Tuple[
    Dict[Rule, GuardStatus],
    Set[Tuple[str, str]],
    Set[Tuple[str, str]],
]:
    results: Dict[Rule, GuardStatus] = {}
    present_members: Set[Tuple[str, str]] = set()
    mixed_absent_members: Set[Tuple[str, str]] = set()
    absent_members: Set[Tuple[str, str]] = set()

    for rule in expandable:
        any_present = False
        any_absent = False
        rule_absent_members: List[Tuple[str, str]] = []
        for expanded in resolver.expand_rule(rule):
            pairs = get_membership_pairs(rule, expanded, resolver)
            if is_expansion_present(expanded, rules):
                any_present = True
                present_members.update(pairs)
            else:
                any_absent = True
                rule_absent_members.extend(pairs)
                absent_members.update(pairs)

        if not any_present and not any_absent:
            status = GuardStatus.EMPTY
        elif not any_absent:
            status = GuardStatus.ALL_PRESENT
        elif not any_present:
            status = GuardStatus.ALL_ABSENT
        else:
            status = GuardStatus.MIXED
            mixed_absent_members.update(rule_absent_members)

        results[rule] = status

    exclusions = mixed_absent_members - present_members
    absent_memberships = absent_members - present_members
    return results, exclusions, absent_memberships


class ExpandedGuardPolicyProvider(PolicyProvider):
    def __init__(self, verbose: bool):
        super().__init__(PolicyExpandedGuardOrigin)

        self.__verbose = verbose

    def resolve_metadata(
        self,
        policy_index: PolicyIndex,
        policy_type: PolicyType,
        requested: Optional[PolicyMetadata],
    ):
        assert isinstance(policy_type.origin, PolicyExpandedGuardOrigin)

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
        assert isinstance(policy_type.origin, PolicyExpandedGuardOrigin)
        origin = policy_type.origin

        source_policy = policy_index.find(origin.source, metadata)
        if source_policy is None:
            return None

        reference_policy = policy_index.find(origin.reference)
        if reference_policy is None:
            return source_policy.copy(
                policy_type=policy_type,
                rules=source_policy.rules,
                genfs_rules=source_policy.genfs_rules,
                contexts=source_policy.contexts,
            )

        expander_policy = policy_index.get(
            origin.expander_source,
            reference_policy.metadata,
        )
        resolver = Resolver(expander_policy.rules)

        expandable = [
            rule
            for rule in source_policy.rules
            if rule.rule_type in EXPAND_TYPES
        ]

        excluded: Set[Tuple[str, str]] = set()
        results: Dict[Rule, GuardStatus] = {}
        absent_memberships: Set[Tuple[str, str]] = set()
        passes = 0
        while True:
            passes += 1
            results, exclusions, pass_absent = classify_rules(
                expandable,
                resolver,
                reference_policy.rules,
            )
            if passes == 1:
                absent_memberships = pass_absent
            added = False
            for attribute, member in exclusions - excluded:
                excluded.add((attribute, member))
                resolver.exclude_member(attribute, member)
                added = True
            if not added:
                break

        guarded_rules = RuleContainer()
        counts = {status: 0 for status in GuardStatus}
        for rule, status in results.items():
            counts[status] += 1
            if status == GuardStatus.ALL_ABSENT:
                guarded_rules.add(rule)

        for membership in get_absent_memberships(
            source_policy.rules,
            absent_memberships,
        ):
            guarded_rules.add(membership)

        color_print(
            f'Guarded {source_policy.pretty_name}: '
            f'absent={counts[GuardStatus.ALL_ABSENT]} '
            f'present={counts[GuardStatus.ALL_PRESENT]} '
            f'mixed={counts[GuardStatus.MIXED]} '
            f'empty={counts[GuardStatus.EMPTY]} '
            f'(passes={passes}, excluded={len(excluded)})',
            color=Color.GREEN,
        )

        new_policy = source_policy.copy(
            policy_type=policy_type,
            rules=source_policy.rules,
            genfs_rules=source_policy.genfs_rules,
            contexts=source_policy.contexts,
        )

        guarded = dict(source_policy.guarded_rules or {})
        for rule in guarded_rules:
            assert rule not in guarded, rule
            guarded[rule] = origin.guard
        new_policy.guarded_rules = guarded

        new_policy.absent_memberships = {
            pair: origin.guard for pair in absent_memberships
        }

        return new_policy

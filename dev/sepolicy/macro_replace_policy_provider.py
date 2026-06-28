# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from sepolicy.class_set import ClassSet
from sepolicy.expander import EXPAND_TYPES, varargs_subset
from sepolicy.match import replace_macro_rules
from sepolicy.policy import (
    PolicyIndex,
    PolicyMacroReplaceOrigin,
    PolicyMetadata,
    PolicyProvider,
    PolicyType,
)
from sepolicy.rule import Rule, RuleType
from sepolicy.rule_container import RuleContainer
from sepolicy.varargs import Ioctls, Perms
from utils.utils import Color, color_print

GUARDABLE_TYPES = EXPAND_TYPES | frozenset({RuleType.TYPEATTRIBUTE})


def guardable_atoms(rule: Rule) -> List[Rule]:
    if rule.is_macro:
        assert rule.expanded_rules is not None
        return [
            expanded_rule
            for expanded_rule in rule.expanded_rules
            if expanded_rule.rule_type in GUARDABLE_TYPES
        ]

    if rule.rule_type == RuleType.TYPEATTRIBUTE:
        return [rule]

    if rule.rule_type not in EXPAND_TYPES:
        return []

    class_name = rule.parts[2]
    if isinstance(class_name, ClassSet):
        return [
            Rule(
                rule.rule_type,
                (rule.parts[0], rule.parts[1], cn, *rule.parts[3:]),
                rule.varargs,
            )
            for cn in class_name
        ]
    return [rule]


def redundant(atom: Rule, unguarded: RuleContainer) -> bool:
    match_keys = (atom.rule_type, *atom.parts, None)
    return any(
        varargs_subset(atom.varargs, match.varargs)
        for match in unguarded.match(match_keys)
        if isinstance(atom.varargs, (Perms, Ioctls))
        and isinstance(match.varargs, (Perms, Ioctls))
    )


def assign_guards(
    rules: RuleContainer,
    incoming: Dict[Rule, str],
) -> Tuple[Dict[Rule, str], int]:
    guards: Dict[Rule, str] = {}
    splits: List[Tuple[Rule, str, List[Rule]]] = []
    unguarded = RuleContainer()
    for rule in rules:
        atoms = guardable_atoms(rule)
        if not atoms:
            continue

        relevant = [
            atom
            for atom in atoms
            if atom.rule_type != RuleType.TYPEATTRIBUTE or atom in incoming
        ]
        in_guard = [atom for atom in relevant if atom in incoming]
        if not in_guard:
            for atom in atoms:
                if atom.rule_type in EXPAND_TYPES:
                    unguarded.add(atom)
            continue

        guard = incoming[in_guard[0]]
        assert all(incoming[atom] == guard for atom in in_guard), rule
        if len(in_guard) == len(relevant):
            guards[rule] = guard
        else:
            present = [atom for atom in relevant if atom not in incoming]
            splits.append((rule, guard, present))

    split = 0
    for rule, guard, present in splits:
        if all(redundant(atom, unguarded) for atom in present):
            guards[rule] = guard
        else:
            split += 1

    return guards, split


def finalize_guards(
    guards: Dict[Rule, str],
    incoming: Dict[Rule, str],
    split: int,
    name: str,
) -> Dict[Rule, str]:
    covered: Set[Rule] = set()
    for rule in guards:
        covered.update(guardable_atoms(rule))

    lost = sum(1 for rule in incoming if rule not in covered)
    if split or lost:
        color_print(
            f'Guard propagation in {name}: split={split} lost={lost}',
            color=Color.YELLOW,
        )

    return guards


def guard_membership_macros(
    rules: RuleContainer,
    guards: Dict[Rule, str],
    absent_memberships: Dict[Tuple[str, str], str],
):
    if not absent_memberships:
        return

    for rule in rules:
        if not rule.is_macro or rule in guards or rule.expanded_rules is None:
            continue

        guard = None
        for atom in rule.expanded_rules:
            if atom.rule_type != RuleType.TYPEATTRIBUTE:
                continue

            member, attribute = atom.parts[0], atom.parts[1]
            if isinstance(member, str) and isinstance(attribute, str):
                guard = absent_memberships.get((attribute, member))
                if guard is not None:
                    break

        if guard is not None:
            guards[rule] = guard


class MacroReplacePolicyProvider(PolicyProvider):
    def __init__(self, verbose: bool):
        super().__init__(PolicyMacroReplaceOrigin)

        self.__verbose = verbose

    def resolve_metadata(
        self,
        policy_index: PolicyIndex,
        policy_type: PolicyType,
        requested: Optional[PolicyMetadata],
    ):
        assert isinstance(policy_type.origin, PolicyMacroReplaceOrigin)

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
        assert isinstance(policy_type.origin, PolicyMacroReplaceOrigin)

        source_policy = policy_index.find(
            policy_type.origin.source,
            metadata,
        )
        if source_policy is None:
            return None

        assert source_policy.rule_matches is not None

        rules = RuleContainer(source_policy.rules)

        replace_macro_rules(
            rules,
            source_policy.rule_matches,
            source_policy.pretty_name,
            self.__verbose,
        )

        guards: Dict[Rule, str] = {}
        split = 0
        if source_policy.guarded_rules is not None:
            guards, split = assign_guards(rules, source_policy.guarded_rules)

        guard_membership_macros(
            rules,
            guards,
            source_policy.absent_memberships or {},
        )

        new_policy = source_policy.copy(
            policy_type=policy_type,
            rules=rules,
            genfs_rules=source_policy.genfs_rules,
            contexts=source_policy.contexts,
        )
        if source_policy.guarded_rules is not None:
            new_policy.guarded_rules = finalize_guards(
                guards,
                source_policy.guarded_rules,
                split,
                source_policy.pretty_name,
            )
        return new_policy

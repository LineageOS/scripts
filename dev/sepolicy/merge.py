# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import List, Optional, Set

from sepolicy.class_set import ClassSet
from sepolicy.rule import IOCTL_RULE_TYPES, Rule
from sepolicy.rule_container import LineMark, RuleContainer
from sepolicy.varargs import Ioctls


def ioctl_same_ioctl_key(rule: Rule, index: int):
    if not isinstance(rule.parts[index], str):
        return None

    return (
        rule.rule_type,
        rule.parts[:index],
        rule.parts[index + 1 :],
        rule.varargs,
    )


def merge_ioctl_rules_same_ioctls(rules: List[Rule], index: int):
    group_rules: List[Rule] = []
    new_rules: List[Rule] = []

    def merge_group_rules():
        nonlocal group_rules
        nonlocal new_rules

        if not group_rules:
            return

        if len(group_rules) == 1:
            new_rules.append(group_rules[0])
            group_rules = []
            return

        objects: List[str] = []
        for rule in group_rules:
            obj = rule.parts[index]
            assert isinstance(obj, str)
            objects.append(obj)

        base_rule = group_rules[0]
        group_rules = []

        new_rule = Rule(
            base_rule.rule_type,
            (
                *base_rule.parts[:index],
                ClassSet(objects, objects),
                *base_rule.parts[index + 1 :],
            ),
            base_rule.varargs,
        )
        new_rules.append(new_rule)

    last_key = None
    for rule in rules:
        key = ioctl_same_ioctl_key(rule, index)
        if key is None:
            merge_group_rules()
            new_rules.append(rule)
            last_key = None
            continue

        if last_key is not None and key != last_key:
            merge_group_rules()

        group_rules.append(rule)
        last_key = key

    merge_group_rules()

    return new_rules


def ioctl_same_class_key(rule: Rule):
    return (
        rule.rule_type,
        rule.parts,
    )


def merge_ioctl_rules_same_class(rules: List[Rule]):
    group_rules: List[Rule] = []
    new_rules: List[Rule] = []

    def merge_group_rules():
        nonlocal group_rules
        nonlocal new_rules

        if not group_rules:
            return

        if len(group_rules) == 1:
            new_rules.append(group_rules[0])
            group_rules = []
            return

        merged_ioctls = None
        for rule in group_rules:
            assert isinstance(rule.varargs, Ioctls)
            if merged_ioctls is None:
                merged_ioctls = rule.varargs
            else:
                merged_ioctls = merged_ioctls.merge(rule.varargs)

        base_rule = group_rules[0]
        group_rules = []

        new_rule = Rule(
            base_rule.rule_type,
            base_rule.parts,
            merged_ioctls,
        )
        new_rules.append(new_rule)

    last_key = None
    for rule in rules:
        key = ioctl_same_class_key(rule)
        if last_key is not None and key != last_key:
            merge_group_rules()

        group_rules.append(rule)
        last_key = key

    merge_group_rules()

    return new_rules


def expand_ioctl_rules_class_sets(rules: List[Rule], index: int):
    new_rules: List[Rule] = []
    for rule in rules:
        part = rule.parts[index]

        if not isinstance(part, ClassSet):
            new_rules.append(rule)
            continue

        for cls in part:
            new_rule = Rule(
                rule.rule_type,
                (
                    *rule.parts[:index],
                    cls,
                    *rule.parts[index + 1 :],
                ),
                rule.varargs,
            )
            new_rules.append(new_rule)

    return new_rules


def merge_ioctl_rules(rules: List[Rule]):
    assert rules

    if len(rules) == 1:
        return rules

    new_rules = rules

    # See system/sepolicy/private/app_neverallows.te:128
    # neverallowxperm all_untrusted_apps domain:{ icmp_socket rawip_socket tcp_socket udp_socket } ioctl priv_sock_ioctls;
    # priv_sock_ioctls is multi-line which ends up generating multiple rules for
    # for each socket type, and since all_untrusted_apps is a class set, we end
    # up with a lot of ioctls which are not mergeable consecutively

    # Merge socket types
    new_rules = merge_ioctl_rules_same_ioctls(new_rules, 2)
    # Merge source domains
    new_rules = merge_ioctl_rules_same_ioctls(new_rules, 0)
    # Merge target domains
    new_rules = merge_ioctl_rules_same_ioctls(new_rules, 1)
    # Merge ioctls
    new_rules = merge_ioctl_rules_same_class(new_rules)
    # Expand socket types
    new_rules = expand_ioctl_rules_class_sets(new_rules, 2)
    # Expand source domains
    new_rules = expand_ioctl_rules_class_sets(new_rules, 0)
    # Expand target domains
    new_rules = expand_ioctl_rules_class_sets(new_rules, 1)

    return new_rules


def is_ioctl_rule_mergeable(rule: Rule):
    return rule.rule_type in IOCTL_RULE_TYPES


def can_ioctl_rule_be_merged(
    rule: Rule,
    mark: Optional[LineMark],
    rules: List[Rule],
    marks: Set[LineMark],
):
    if not rules:
        return False

    base_rule = rules[0]
    if rule.rule_type != base_rule.rule_type:
        return False

    if mark is not None and marks and mark not in marks:
        return False

    return True


def merge_current_rules(
    mergeable_rules: List[Rule],
    mergeable_marks: Set[LineMark],
    rules: RuleContainer,
):
    if not mergeable_rules:
        return

    merged_rules = merge_ioctl_rules(mergeable_rules)
    for merged_rule in merged_rules:
        rules.add(merged_rule, mergeable_marks)

    mergeable_rules.clear()
    mergeable_marks.clear()


def add_mergeable_rule(
    rule: Rule,
    mark: Optional[LineMark],
    mergeable_rules: List[Rule],
    mergeable_marks: Set[LineMark],
    rules: RuleContainer,
):
    if not is_ioctl_rule_mergeable(rule):
        merge_current_rules(mergeable_rules, mergeable_marks, rules)
        rules.add(rule, (mark,) if mark is not None else None)
        return

    if not can_ioctl_rule_be_merged(
        rule,
        mark,
        mergeable_rules,
        mergeable_marks,
    ):
        merge_current_rules(mergeable_rules, mergeable_marks, rules)

    mergeable_rules.append(rule)
    if mark is not None:
        mergeable_marks.add(mark)

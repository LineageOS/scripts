# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from collections import defaultdict
from typing import DefaultDict, List, Set, Tuple

from sepolicy.rule import IOCTL_RULE_TYPES, Rule, rule_part


def merge_ioctl_rules(rules: List[Rule]):
    new_rules: List[Rule] = []

    ioctl_rules_map: DefaultDict[
        Tuple[rule_part, ...],
        List[Rule],
    ] = defaultdict(list)

    for rule in rules:
        # TODO: merge other types of rules and remove the splitting from
        # source policy
        # Might not work for recovery where there are no comments

        if rule.rule_type not in IOCTL_RULE_TYPES:
            new_rules.append(rule)
            continue

        ioctl_rules_map[(rule.rule_type, *rule.parts)].append(rule)

    for same_rules in ioctl_rules_map.values():
        if len(same_rules) <= 1:
            new_rules.extend(same_rules)
            continue

        first_rule = same_rules[0]

        varargs: Set[str] = set()
        for rule in same_rules:
            varargs.update(rule.varargs)

        new_rule = Rule(
            first_rule.rule_type,
            first_rule.parts,
            tuple(varargs),
        )
        new_rules.append(new_rule)

    return new_rules


def merge_rules(rules: List[Rule]):
    if len(rules) <= 1:
        return rules

    return merge_ioctl_rules(rules)

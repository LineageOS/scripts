# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import unittest
from typing import Iterable, List, Optional, Set, Tuple

from sepolicy.merge import (
    add_mergeable_rule,
    merge_current_rules,
    merge_ioctl_rules,
)
from sepolicy.rule import Rule, RuleType
from sepolicy.rule_container import LineMark, RuleContainer
from sepolicy.tests.helpers import allow
from sepolicy.varargs import Ioctls


def allowx(
    src: str,
    dst: str,
    class_name: str,
    ranges: Iterable[Tuple[int, int]],
    rule_type: str = RuleType.ALLOWXPERM,
):
    return Rule(rule_type, (src, dst, class_name, 'ioctl'), Ioctls(ranges))


def add_all(rules_marks: List[Tuple[Rule, Optional[LineMark]]]):
    rules = RuleContainer()
    mergeable_rules: List[Rule] = []
    mergeable_marks: Set[LineMark] = set()

    for rule, mark in rules_marks:
        add_mergeable_rule(rule, mark, mergeable_rules, mergeable_marks, rules)
    merge_current_rules(mergeable_rules, mergeable_marks, rules)

    return rules


class MergeIoctlRulesTest(unittest.TestCase):
    def test_merges_consecutive_ioctls(self):
        merged = merge_ioctl_rules(
            [
                allowx('vold', 'block_device', 'blk_file', [(0x1, 0x1)]),
                allowx('vold', 'block_device', 'blk_file', [(0x2, 0x3)]),
            ]
        )

        self.assertEqual(
            merged,
            [allowx('vold', 'block_device', 'blk_file', [(0x1, 0x3)])],
        )

    def test_merges_interleaved_classes(self):
        merged = merge_ioctl_rules(
            [
                allowx('app', 'domain', 'tcp_socket', [(0x1, 0x1)]),
                allowx('app', 'domain', 'udp_socket', [(0x1, 0x1)]),
                allowx('app', 'domain', 'tcp_socket', [(0x5, 0x5)]),
                allowx('app', 'domain', 'udp_socket', [(0x5, 0x5)]),
            ]
        )

        self.assertEqual(
            set(merged),
            {
                allowx(
                    'app',
                    'domain',
                    'tcp_socket',
                    [(0x1, 0x1), (0x5, 0x5)],
                ),
                allowx(
                    'app',
                    'domain',
                    'udp_socket',
                    [(0x1, 0x1), (0x5, 0x5)],
                ),
            },
        )

    def test_keeps_different_targets(self):
        rules = [
            allowx('vold', 'block_device', 'blk_file', [(0x1, 0x1)]),
            allowx('vold', 'userdata_block_device', 'blk_file', [(0x2, 0x2)]),
        ]

        self.assertEqual(set(merge_ioctl_rules(rules)), set(rules))


class AddMergeableRuleTest(unittest.TestCase):
    def test_merges_rules_from_same_line(self):
        mark = LineMark('vold.te', 1)

        rules = add_all(
            [
                (allowx('vold', 'blk', 'blk_file', [(0x1, 0x1)]), mark),
                (allowx('vold', 'blk', 'blk_file', [(0x2, 0x2)]), mark),
            ]
        )

        merged = allowx('vold', 'blk', 'blk_file', [(0x1, 0x2)])
        self.assertEqual(list(rules), [merged])
        self.assertEqual(rules.marks(merged), {mark})

    def test_keeps_rules_from_different_lines(self):
        first = allowx('vold', 'blk', 'blk_file', [(0x1, 0x1)])
        second = allowx('vold', 'blk', 'blk_file', [(0x2, 0x2)])

        rules = add_all(
            [
                (first, LineMark('vold.te', 1)),
                (second, LineMark('vold.te', 2)),
            ]
        )

        self.assertEqual(set(rules), {first, second})

    def test_other_rule_ends_group(self):
        first = allowx('vold', 'blk', 'blk_file', [(0x1, 0x1)])
        other = allow('vold', 'blk', 'blk_file', ['ioctl'])
        second = allowx('vold', 'blk', 'blk_file', [(0x2, 0x2)])

        rules = add_all([(first, None), (other, None), (second, None)])

        self.assertEqual(set(rules), {first, other, second})

    def test_rule_type_ends_group(self):
        first = allowx('vold', 'blk', 'blk_file', [(0x1, 0x1)])
        second = allowx(
            'vold',
            'blk',
            'blk_file',
            [(0x2, 0x2)],
            RuleType.DONTAUDITXPERM,
        )

        rules = add_all([(first, None), (second, None)])

        self.assertEqual(set(rules), {first, second})


if __name__ == '__main__':
    unittest.main()

# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import unittest
from typing import List, Optional

from sepolicy.cil_rule import CilRuleParser, unpack_cil_line
from sepolicy.conditional_type import ConditionalType
from sepolicy.rule import Rule, RuleType
from sepolicy.varargs import Perms, TypeTransitionTag


def parse(lines: List[str], version: Optional[str] = None):
    rules: List[Rule] = []
    parser = CilRuleParser(
        conditional_types_map={},
        reference_conditional_types_maps=[],
        add_rule=rules.append,
        add_genfs_rule=None,
        version=version,
    )

    for line in lines:
        parser.parse_line(line, unpack_cil_line(line))

    return rules


class GeneratedAttributeTest(unittest.TestCase):
    def test_partition_module_name(self):
        rules = parse(
            [
                '(typeattribute product_typeattr_1326)',
                (
                    '(typeattributeset product_typeattr_1326 '
                    '(and (domain ) (not (crash_dump better_bug_app ))))'
                ),
                (
                    '(allow product_typeattr_1326 better_bug_app '
                    '(process (ptrace)))'
                ),
            ]
        )

        self.assertEqual(
            rules,
            [
                Rule(
                    RuleType.ALLOW,
                    (
                        ConditionalType(
                            ['domain'],
                            ['crash_dump', 'better_bug_app'],
                            False,
                        ),
                        'better_bug_app',
                        'process',
                    ),
                    Perms(['ptrace'], False),
                ),
            ],
        )

    def test_versioned_base_module(self):
        rules = parse(
            [
                (
                    '(typeattributeset base_typeattr_311_202604 '
                    '(not (system_server_wrapfd_202604 app_userfaultfd)))'
                ),
                '(allow app base_typeattr_311_202604 (anon_inode (read)))',
            ],
            version='202604',
        )

        self.assertEqual(
            rules,
            [
                Rule(
                    RuleType.ALLOW,
                    (
                        'app',
                        ConditionalType(
                            [],
                            ['system_server_wrapfd', 'app_userfaultfd'],
                            False,
                        ),
                        'anon_inode',
                    ),
                    Perms(['read'], False),
                ),
            ],
        )


class TypeTransitionTest(unittest.TestCase):
    def test_named(self):
        rules = parse(
            [
                (
                    '(typetransition app app anon_inode "[io_uring]" '
                    'app_block_io_uring)'
                ),
            ]
        )

        self.assertEqual(
            rules,
            [
                Rule(
                    RuleType.TYPE_TRANSITION,
                    ('app', 'app', 'anon_inode', 'app_block_io_uring'),
                    TypeTransitionTag('"[io_uring]"'),
                ),
            ],
        )


if __name__ == '__main__':
    unittest.main()

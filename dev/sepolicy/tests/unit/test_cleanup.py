# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import unittest

from sepolicy.cleanup_policy_provider import remove_covered_rules
from sepolicy.rule import Rule, RuleType
from sepolicy.rule_container import RuleContainer
from sepolicy.tests.helpers import allow, member
from sepolicy.varargs import TypeTransitionTag


class RemoveCoveredRulesTest(unittest.TestCase):
    def setUp(self):
        self.covering = RuleContainer(
            [
                member('app', 'domain'),
                member('vendor_overlay_file', 'vendor_file_type'),
                allow(
                    'domain',
                    'vendor_file_type',
                    'file',
                    ['read', 'getattr', 'map', 'open'],
                ),
                allow(
                    'app',
                    'vendor_overlay_file',
                    'file',
                    ['ioctl', 'lock', 'watch', 'watch_reads'],
                ),
            ]
        )

    def test_drops_fully_covered(self):
        rules = RuleContainer(
            [
                allow(
                    'app',
                    'vendor_overlay_file',
                    'file',
                    ['getattr', 'ioctl', 'lock', 'map', 'open', 'read'],
                ),
            ]
        )

        self.assertEqual(len(remove_covered_rules(rules, self.covering)), 0)

    def test_keeps_partially_covered_unchanged(self):
        rule = allow('app', 'vendor_overlay_file', 'file', ['read', 'write'])

        result = remove_covered_rules(RuleContainer([rule]), self.covering)

        self.assertEqual(list(result), [rule])

    def test_non_access_rules_are_removed_exactly(self):
        kept = Rule(
            RuleType.TYPE_TRANSITION,
            ('app', 'app', 'anon_inode', 'app_wrapfd'),
            TypeTransitionTag('"[wrapfd]"'),
        )
        removed = member('app', 'domain')

        result = remove_covered_rules(
            RuleContainer([kept, removed]),
            self.covering,
        )

        self.assertEqual(list(result), [kept])


if __name__ == '__main__':
    unittest.main()

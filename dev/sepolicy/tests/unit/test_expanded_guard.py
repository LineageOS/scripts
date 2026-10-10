# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import unittest

from sepolicy.expanded_guard_policy_provider import GuardStatus, classify_rules
from sepolicy.expander import Coverage, Resolver
from sepolicy.rule import Rule, RuleType
from sepolicy.rule_container import RuleContainer
from sepolicy.tests.helpers import allow, member

TYPES = RuleContainer(
    [
        Rule(RuleType.ATTRIBUTE, ('domain',)),
        Rule(RuleType.ATTRIBUTE, ('appdomain',)),
        Rule(RuleType.ATTRIBUTE, ('fs_type',)),
        Rule(RuleType.TYPE, ('app',)),
        Rule(RuleType.TYPE, ('kernel',)),
        Rule(RuleType.TYPE, ('cgroup_app',)),
        member('app', 'domain'),
        member('app', 'appdomain'),
        member('kernel', 'domain'),
        member('cgroup_app', 'fs_type'),
    ]
)


class ClassifyRulesTest(unittest.TestCase):
    def setUp(self):
        self.resolver = Resolver(TYPES)

    def classify(self, rule: Rule, *recovery: Rule):
        coverage = Coverage(RuleContainer([*TYPES, *recovery]))
        results, _, _ = classify_rules([rule], self.resolver, coverage)
        return results[rule]

    def test_present_through_broader_rule(self):
        rule = allow('appdomain', 'cgroup_app', 'dir', ['getattr', 'search'])

        status = self.classify(
            rule,
            allow('domain', 'fs_type', 'dir', ['getattr']),
            allow('appdomain', 'cgroup_app', 'dir', ['search']),
        )

        self.assertEqual(status, GuardStatus.ALL_PRESENT)

    def test_absent(self):
        rule = allow('appdomain', 'cgroup_app', 'dir', ['getattr', 'search'])

        status = self.classify(
            rule,
            allow('appdomain', 'cgroup_app', 'dir', ['search']),
        )

        self.assertEqual(status, GuardStatus.ALL_ABSENT)


if __name__ == '__main__':
    unittest.main()

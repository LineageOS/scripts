# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import unittest

from sepolicy.macro_replace_policy_provider import (
    assign_guards,
    guard_membership_macros,
)
from sepolicy.rule import Rule
from sepolicy.rule_container import RuleContainer
from sepolicy.tests.helpers import allow, member


def macro(name: str, *expanded: Rule, args: tuple = ('app',)):
    return Rule(name, args, is_macro=True, expanded_rules=frozenset(expanded))


CALL = allow('app', 'system_server', 'binder', ['call', 'transfer'])
TRANSFER = allow('system_server', 'app', 'binder', ['transfer'])
FD = allow('app', 'system_server', 'fd', ['use'])
BINDER_CALL = macro(
    'binder_call',
    CALL,
    TRANSFER,
    FD,
    args=('app', 'system_server'),
)


class AssignGuardsTest(unittest.TestCase):
    def test_fully_guarded_macro(self):
        incoming = {
            CALL: 'not_recovery',
            TRANSFER: 'not_recovery',
            FD: 'not_recovery',
        }

        guards, split = assign_guards(RuleContainer([BINDER_CALL]), incoming)

        self.assertEqual(guards, {BINDER_CALL: 'not_recovery'})
        self.assertEqual(split, 0)

    def test_partially_guarded_macro_is_split(self):
        incoming = {CALL: 'not_recovery'}

        guards, split = assign_guards(RuleContainer([BINDER_CALL]), incoming)

        self.assertEqual(guards, {})
        self.assertEqual(split, 1)

    def test_partially_guarded_macro_with_redundant_rest(self):
        incoming = {CALL: 'not_recovery'}
        rules = RuleContainer([BINDER_CALL, TRANSFER, FD])

        guards, split = assign_guards(rules, incoming)

        self.assertEqual(guards, {BINDER_CALL: 'not_recovery'})
        self.assertEqual(split, 0)

    def test_unguarded_typeattribute_is_ignored(self):
        domain_member = member('app', 'domain')
        net_domain = macro('net_domain', domain_member, FD)

        guards, _ = assign_guards(
            RuleContainer([net_domain]),
            {FD: 'not_recovery'},
        )

        self.assertEqual(guards, {net_domain: 'not_recovery'})

    def test_plain_rule(self):
        guards, _ = assign_guards(
            RuleContainer([CALL, FD]),
            {CALL: 'not_recovery'},
        )

        self.assertEqual(guards, {CALL: 'not_recovery'})


class GuardMembershipMacrosTest(unittest.TestCase):
    def test_absent_membership(self):
        hal_server = macro(
            'hal_server_domain',
            member('app', 'hal_face_debug_server'),
            FD,
            args=('app', 'hal_face_debug'),
        )
        guards = {}

        guard_membership_macros(
            RuleContainer([hal_server, BINDER_CALL]),
            guards,
            {('hal_face_debug_server', 'app'): 'not_recovery'},
        )

        self.assertEqual(guards, {hal_server: 'not_recovery'})


if __name__ == '__main__':
    unittest.main()

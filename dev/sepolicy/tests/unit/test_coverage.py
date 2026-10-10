# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import unittest
from typing import Iterable, Tuple

from sepolicy.expander import Coverage
from sepolicy.rule import Rule, RuleType
from sepolicy.rule_container import RuleContainer
from sepolicy.tests.helpers import allow, member
from sepolicy.varargs import Ioctls, Perms


def coverage(*rules: Rule):
    return Coverage(RuleContainer(rules))


class CoverageTest(unittest.TestCase):
    def test_direct(self):
        c = coverage(allow('app', 'data_file', 'file', ['read', 'open']))

        self.assertTrue(
            c.uncovered(allow('app', 'data_file', 'file', ['read'])).is_empty()
        )

    def test_remaining(self):
        c = coverage(allow('app', 'data_file', 'file', ['read']))

        self.assertEqual(
            c.uncovered(allow('app', 'data_file', 'file', ['read', 'open'])),
            Perms(['open'], False),
        )

    def test_type_attributes(self):
        c = coverage(
            member('app', 'domain'),
            member('data_file', 'file_type'),
            allow('domain', 'file_type', 'file', ['getattr']),
            allow('app', 'data_file', 'file', ['read', 'open']),
        )

        self.assertTrue(
            c.uncovered(
                allow('app', 'data_file', 'file', ['getattr', 'read', 'open'])
            ).is_empty()
        )

    def test_attribute_superset(self):
        c = coverage(
            member('app', 'appdomain'),
            member('app', 'domain'),
            member('kernel', 'domain'),
            member('cgroup_app', 'fs_type'),
            allow('domain', 'fs_type', 'dir', ['getattr']),
            allow('appdomain', 'cgroup_app', 'dir', ['search', 'open']),
        )

        self.assertTrue(
            c.uncovered(
                allow('appdomain', 'cgroup_app', 'dir', ['getattr', 'search'])
            ).is_empty()
        )

    def test_attribute_subset_does_not_cover(self):
        c = coverage(
            member('app', 'appdomain'),
            member('app', 'domain'),
            member('kernel', 'domain'),
            allow('appdomain', 'data_file', 'file', ['read']),
        )

        self.assertEqual(
            c.uncovered(allow('domain', 'data_file', 'file', ['read'])),
            Perms(['read'], False),
        )

    def test_self(self):
        c = coverage(
            member('app', 'domain'),
            allow('domain', 'self', 'process', ['fork']),
            allow('domain', 'domain', 'process', ['sigchld']),
        )

        self.assertTrue(
            c.uncovered(
                allow('app', 'self', 'process', ['fork', 'sigchld'])
            ).is_empty()
        )

    def test_self_does_not_cover_other_target(self):
        c = coverage(
            member('app', 'domain'),
            member('kernel', 'domain'),
            allow('domain', 'self', 'process', ['fork']),
        )

        self.assertEqual(
            c.uncovered(allow('app', 'kernel', 'process', ['fork'])),
            Perms(['fork'], False),
        )

    def test_rule_type(self):
        c = coverage(
            Rule(
                RuleType.DONTAUDIT,
                ('app', 'data_file', 'file'),
                Perms(['read'], False),
            ),
        )

        self.assertEqual(
            c.uncovered(allow('app', 'data_file', 'file', ['read'])),
            Perms(['read'], False),
        )

    def test_ioctls(self):
        def allowx(src: str, ranges: Iterable[Tuple[int, int]]):
            return Rule(
                RuleType.ALLOWXPERM,
                (src, 'block_device', 'blk_file', 'ioctl'),
                Ioctls(ranges),
            )

        c = coverage(
            member('vold', 'domain'),
            allowx('domain', [(0x1278, 0x1279)]),
            allowx('vold', [(0x127A, 0x127A)]),
        )

        self.assertTrue(
            c.uncovered(allowx('vold', [(0x1278, 0x127A)])).is_empty()
        )
        self.assertEqual(
            c.uncovered(allowx('vold', [(0x1278, 0x127B)])),
            Ioctls([(0x127B, 0x127B)]),
        )


if __name__ == '__main__':
    unittest.main()

# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import unittest

from sepolicy.expander import Coverage
from sepolicy.restore_optimized_policy_provider import restore_optimized_rule
from sepolicy.rule import RuleType
from sepolicy.rule_container import RuleContainer
from sepolicy.tests.helpers import R_DIR_PERMS, allow, member

RW_DIR_PERMS = R_DIR_PERMS | {'add_name', 'remove_name', 'write'}

CLASS_PERMS = {
    'dir': [
        ('rw_dir_perms', RW_DIR_PERMS),
        ('r_dir_perms', R_DIR_PERMS),
    ],
}


OPTIMIZED = allow(
    'hal_bootctl_default',
    'rootfs',
    'dir',
    ['ioctl', 'lock', 'open', 'read', 'watch', 'watch_reads'],
)


class RestoreOptimizedRuleTest(unittest.TestCase):
    def test_restores_smallest_macro(self):
        coverage = Coverage(
            RuleContainer(
                [
                    member('hal_bootctl_default', 'domain'),
                    member('rootfs', 'fs_type'),
                    allow('domain', 'fs_type', 'dir', ['getattr']),
                    allow('domain', 'rootfs', 'dir', ['search', 'write']),
                    OPTIMIZED,
                ]
            )
        )

        self.assertEqual(
            restore_optimized_rule(OPTIMIZED, coverage, CLASS_PERMS),
            allow('hal_bootctl_default', 'rootfs', 'dir', R_DIR_PERMS),
        )

    def test_keeps_rule_without_coverage(self):
        coverage = Coverage(
            RuleContainer(
                [
                    member('hal_bootctl_default', 'domain'),
                    allow('domain', 'rootfs', 'dir', ['getattr']),
                    OPTIMIZED,
                ]
            )
        )

        self.assertIs(
            restore_optimized_rule(OPTIMIZED, coverage, CLASS_PERMS),
            OPTIMIZED,
        )

    def test_keeps_rule_matching_macro(self):
        unoptimized = allow('recovery', 'sysfs_scsi', 'dir', R_DIR_PERMS)
        coverage = Coverage(RuleContainer([unoptimized]))

        self.assertIs(
            restore_optimized_rule(unoptimized, coverage, CLASS_PERMS),
            unoptimized,
        )

    def test_keeps_rule_of_class_without_macros(self):
        optimized = allow('app', 'app', 'process', ['fork'])
        coverage = Coverage(RuleContainer([optimized]))

        self.assertIs(
            restore_optimized_rule(optimized, coverage, CLASS_PERMS),
            optimized,
        )

    def test_dontaudit(self):
        optimized = allow(
            'app',
            'rootfs',
            'dir',
            ['ioctl', 'lock', 'open', 'read', 'watch', 'watch_reads'],
            RuleType.DONTAUDIT,
        )
        coverage = Coverage(
            RuleContainer(
                [
                    allow(
                        'app',
                        'rootfs',
                        'dir',
                        ['getattr', 'search'],
                        RuleType.DONTAUDIT,
                    ),
                    optimized,
                ]
            )
        )

        self.assertEqual(
            restore_optimized_rule(optimized, coverage, CLASS_PERMS),
            allow('app', 'rootfs', 'dir', R_DIR_PERMS, RuleType.DONTAUDIT),
        )


if __name__ == '__main__':
    unittest.main()

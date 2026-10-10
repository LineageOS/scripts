# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import unittest

from sepolicy.rule import Rule, RuleType, is_type_generated
from sepolicy.varargs import ArgVarargs, Ioctls, Types, TypeTransitionTag


class FormatTypeTest(unittest.TestCase):
    def test_with_attributes(self):
        rule = Rule(RuleType.TYPE, ('app',), Types({'domain', 'appdomain'}))

        self.assertEqual(str(rule), 'type app, appdomain, domain;')

    def test_without_attributes(self):
        rule = Rule(RuleType.TYPE, ('app_userfaultfd',), Types(set()))

        self.assertEqual(str(rule), 'type app_userfaultfd;')

    def test_without_varargs(self):
        rule = Rule(RuleType.TYPE, ('app_userfaultfd',))

        self.assertEqual(str(rule), 'type app_userfaultfd;')


class FormatTypeTransitionTest(unittest.TestCase):
    def test_named(self):
        rule = Rule(
            RuleType.TYPE_TRANSITION,
            ('app', 'app', 'anon_inode', 'app_block_io_uring'),
            TypeTransitionTag('"[io_uring]"'),
        )

        self.assertEqual(
            str(rule),
            'type_transition app app:anon_inode app_block_io_uring '
            '"[io_uring]";',
        )

    def test_unnamed(self):
        rule = Rule(
            RuleType.TYPE_TRANSITION,
            ('app', 'tmpfs', 'file', 'appdomain_tmpfs'),
        )

        self.assertEqual(
            str(rule),
            'type_transition app tmpfs:file appdomain_tmpfs;',
        )


class FormatXpermTest(unittest.TestCase):
    def test_argument(self):
        rule = Rule(
            RuleType.ALLOWXPERM,
            ('appdomain', '$1', 'chr_file', 'ioctl'),
            ArgVarargs(3),
        )

        self.assertEqual(
            str(rule),
            'allowxperm appdomain $1:chr_file ioctl { $3 };',
        )


class FormatMacroTest(unittest.TestCase):
    def test_ioctls_argument(self):
        rule = Rule(
            'set_xperm_filter',
            (
                'gpu_device',
                Ioctls([(0x1, 0x1), (0x5, 0x6)]),
                Ioctls([(0x9, 0x9)]),
            ),
            is_macro=True,
        )

        self.assertEqual(
            rule.format(
                class_perms=None,
                ioctls=None,
                ioctl_defines={0x1: 'GPU_INFO', 0x9: 'GPU_DEBUG'},
                nlmsgs=None,
                nlmsg_defines=None,
            ),
            'set_xperm_filter(gpu_device, GPU_INFO 0x5-0x6, GPU_DEBUG)',
        )


class IsTypeGeneratedTest(unittest.TestCase):
    def test_generated(self):
        for name in (
            'base_typeattr_311',
            'base_typeattr_311_202604',
            'system_ext_typeattr_1177',
            'product_typeattr_1323',
        ):
            with self.subTest(name=name):
                self.assertTrue(is_type_generated(name))

    def test_not_generated(self):
        for name in (
            'better_bug_app',
            'base_typeattr_',
            'vendor_typeattr',
            'appdomain',
        ):
            with self.subTest(name=name):
                self.assertFalse(is_type_generated(name))


if __name__ == '__main__':
    unittest.main()

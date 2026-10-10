# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import unittest

from sepolicy.conditional_type import ConditionalType
from sepolicy.rule import Rule, RuleType
from sepolicy.source_rule import (
    SourceRuleParser,
    structure_conditional_types,
    unpack_ioctls,
    unpack_negative_ioctls,
)
from sepolicy.tests.helpers import CLASSMAP, FILE_PERMS, allow, member, parse_te
from sepolicy.varargs import Ioctls, Perms, TypeTransitionTag


class StructureConditionalTypesTest(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(structure_conditional_types('app'), ['app'])

    def test_positive_set(self):
        self.assertEqual(
            structure_conditional_types(['app', 'system_server']),
            ['app', 'system_server'],
        )

    def test_negative(self):
        self.assertEqual(
            structure_conditional_types(['domain', '-app', '-', 'kernel']),
            [ConditionalType(['domain'], ['app', 'kernel'], False)],
        )

    def test_complement(self):
        self.assertEqual(
            structure_conditional_types('~app'),
            [ConditionalType([], ['app'], False)],
        )
        self.assertEqual(
            structure_conditional_types(['app', 'kernel'], all_negatives=True),
            [ConditionalType([], ['app', 'kernel'], False)],
        )

    def test_all(self):
        self.assertEqual(
            structure_conditional_types('*'),
            [ConditionalType([], [], True)],
        )


class UnpackIoctlsTest(unittest.TestCase):
    def test_values_and_ranges(self):
        self.assertEqual(
            unpack_ioctls(['0x5411', '0x5401-0x5403', '0xc0046686']),
            Ioctls([(0x5401, 0x5403), (0x5411, 0x5411), (0x6686, 0x6686)]),
        )

    def test_negative(self):
        self.assertEqual(
            unpack_negative_ioctls(['0x2', '0x5']),
            Ioctls([(0x0, 0x1), (0x3, 0x4), (0x6, 0xFFFF)]),
        )


class SourceRuleParserTest(unittest.TestCase):
    def test_allow_expands_sets(self):
        rules = parse_te('allow { app kernel } data_file:{ file dir } read;')

        self.assertEqual(
            set(rules),
            {
                allow(src, 'data_file', cls, ['read'])
                for src in ('app', 'kernel')
                for cls in ('file', 'dir')
            },
        )

    def test_all_perms(self):
        rules = parse_te('neverallow app data_file:file *;')

        self.assertEqual(
            list(rules),
            [
                Rule(
                    RuleType.NEVERALLOW,
                    ('app', 'data_file', 'file'),
                    Perms(FILE_PERMS, True),
                ),
            ],
        )

    def test_negative_perms(self):
        rules = parse_te('neverallow app data_file:file ~{ read open };')

        self.assertEqual(
            list(rules),
            [
                allow(
                    'app',
                    'data_file',
                    'file',
                    set(FILE_PERMS) - {'read', 'open'},
                    RuleType.NEVERALLOW,
                ),
            ],
        )

    def test_negative_target(self):
        rules = parse_te(
            'neverallow app ~{ app_userfaultfd system_server_wrapfd }'
            ':anon_inode *;'
        )

        target = next(iter(rules)).parts[1]
        self.assertEqual(
            target,
            ConditionalType(
                [],
                ['app_userfaultfd', 'system_server_wrapfd'],
                False,
            ),
        )

    def test_sigchld(self):
        self.assertEqual(
            list(parse_te('allow $3 $1:process sigchld;')),
            [allow('$3', '$1', 'process', ['sigchld'])],
        )

    def test_type_with_attributes(self):
        rules = parse_te('type app, domain, appdomain;')

        self.assertEqual(
            set(rules),
            {
                Rule(RuleType.TYPE, ('app',)),
                member('app', 'domain'),
                member('app', 'appdomain'),
            },
        )

    def test_typeattribute(self):
        rules = parse_te('typeattribute app mlstrustedsubject;')

        self.assertEqual(list(rules), [member('app', 'mlstrustedsubject')])

    def test_type_transition(self):
        rules = parse_te(
            """
type_transition app tmpfs:file appdomain_tmpfs;
type_transition app app:anon_inode app_wrapfd "[wrapfd]";
"""
        )

        self.assertEqual(
            set(rules),
            {
                Rule(
                    RuleType.TYPE_TRANSITION,
                    ('app', 'tmpfs', 'file', 'appdomain_tmpfs'),
                ),
                Rule(
                    RuleType.TYPE_TRANSITION,
                    ('app', 'app', 'anon_inode', 'app_wrapfd'),
                    TypeTransitionTag('"[wrapfd]"'),
                ),
            },
        )

    def test_allowxperm(self):
        rules = parse_te(
            """
allowxperm vold block_device:blk_file ioctl { 0x1278-0x127a 0x1272 };
neverallowxperm app block_device:blk_file ioctl ~{ 0x1 };
"""
        )

        self.assertEqual(
            set(rules),
            {
                Rule(
                    RuleType.ALLOWXPERM,
                    ('vold', 'block_device', 'blk_file', 'ioctl'),
                    Ioctls([(0x1272, 0x1272), (0x1278, 0x127A)]),
                ),
                Rule(
                    RuleType.NEVERALLOWXPERM,
                    ('app', 'block_device', 'blk_file', 'ioctl'),
                    Ioctls([(0x0, 0x0), (0x2, 0xFFFF)]),
                ),
            },
        )

    def test_attribute_and_expandattribute(self):
        rules = parse_te(
            """
attribute hal_face_debug;
expandattribute hal_face_debug true;
"""
        )

        self.assertEqual(
            set(rules),
            {
                Rule(RuleType.ATTRIBUTE, ('hal_face_debug',)),
                Rule(RuleType.EXPANDATTRIBUTE, ('hal_face_debug', 'true')),
            },
        )

    def test_skips_unknown_rule_types(self):
        self.assertEqual(len(parse_te('permissive app;')), 0)

    def test_rejects_invalid_line(self):
        parser = SourceRuleParser(lambda r: None, CLASSMAP)

        with self.assertRaises(ValueError):
            parser.parse_line('allow;')

    def test_genfscon(self):
        self.assertEqual(
            SourceRuleParser.genfscon_from_line(
                'genfscon sysfs /kernel/pixel_stat '
                'u:object_r:sysfs_pixel_stat:s0'
            ),
            Rule(
                RuleType.GENFSCON,
                ('sysfs', '/kernel/pixel_stat', 'sysfs_pixel_stat'),
            ),
        )


if __name__ == '__main__':
    unittest.main()

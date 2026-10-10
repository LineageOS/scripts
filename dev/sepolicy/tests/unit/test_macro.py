# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout

from sepolicy.macro import (
    ArgCondition,
    MacroVariant,
    categorize_macros,
    macro_arity,
    macro_body_variants,
    macro_name_body,
    parse_ioctl_defines,
    parse_ioctls,
    parse_perms,
    rule_body,
)
from sepolicy.rule import Rule, RuleType
from sepolicy.tests.helpers import allow, parse_macros_bodies
from sepolicy.varargs import Ioctls


class MacroNameBodyTest(unittest.TestCase):
    def test_quoted_body(self):
        self.assertEqual(
            macro_name_body("define(`r_file_perms', `{ getattr open read }')"),
            ('r_file_perms', '{ getattr open read }'),
        )

    def test_multiline_body(self):
        self.assertEqual(
            macro_name_body(
                "define(`domain_trans', `\nallow $1 $2:file execute;\n')"
            ),
            ('domain_trans', 'allow $1 $2:file execute;'),
        )

    def test_rule(self):
        self.assertIsNone(macro_name_body('allow a b:file read;'))
        self.assertEqual(
            rule_body('allow a b:file read;'),
            'allow a b:file read;',
        )


class MacroArityTest(unittest.TestCase):
    def test_arity(self):
        self.assertEqual(macro_arity('allow $1 $3_exec:file $2;'), 3)
        self.assertEqual(macro_arity('allow a b:file read;'), 0)


class CategorizeMacrosTest(unittest.TestCase):
    def test_categories(self):
        with redirect_stdout(io.StringIO()):
            macros, class_sets, perms = categorize_macros(
                [
                    ('r_file_perms', '{ read }'),
                    ('dir_file_class_set', '{ file dir }'),
                    ('app_domain', 'allow $1 a:file read;'),
                    ('not_full_treble', ''),
                ]
            )

        self.assertEqual(macros, [('app_domain', 'allow $1 a:file read;')])
        self.assertEqual(class_sets, [('dir_file_class_set', '{ file dir }')])
        self.assertEqual(perms, [('r_file_perms', '{ read }')])


class ParsePermsTest(unittest.TestCase):
    def test_largest_first(self):
        perms = parse_perms(
            [
                ('x_file_perms', '{ getattr execute }'),
                ('rx_file_perms', '{ getattr open read execute }'),
                ('r_file_perms', '{ getattr open read }'),
            ]
        )

        self.assertEqual(
            perms,
            [
                ('rx_file_perms', {'getattr', 'open', 'read', 'execute'}),
                ('r_file_perms', {'getattr', 'open', 'read'}),
                ('x_file_perms', {'getattr', 'execute'}),
            ],
        )


class ParseIoctlsTest(unittest.TestCase):
    def test_values_and_ranges(self):
        ioctls = parse_ioctls(
            [('unpriv_tty_ioctls', '{ 0x5411 0x5401-0x5403 }')],
            is_nlmsg=False,
        )

        self.assertEqual(
            ioctls,
            [
                (
                    'unpriv_tty_ioctls',
                    Ioctls([(0x5401, 0x5403), (0x5411, 0x5411)]),
                ),
            ],
        )

    def test_skips_unexpanded_names(self):
        with redirect_stdout(io.StringIO()):
            ioctls = parse_ioctls(
                [('unpriv_tty_ioctls', '{ TIOCOUTQ 0x5401 }')],
                is_nlmsg=False,
            )

        self.assertEqual(ioctls, [])

    def test_defines_keep_first_name(self):
        defines = parse_ioctl_defines(
            [
                ('TIOCOUTQ', '0x00005411'),
                ('TIOCOUTQ_ALIAS', '0x5411'),
                ('SIOCGIFFLAGS', '0x8913'),
            ],
            verbose=False,
            is_nlmsg=False,
        )

        self.assertEqual(defines, {0x5411: 'TIOCOUTQ', 0x8913: 'SIOCGIFFLAGS'})

    def test_defines_trim_to_two_bytes(self):
        defines = parse_ioctl_defines(
            [
                ('BLKIOMIN', '0x00001278'),
                ('FS_IOC_MEASURE_VERITY', '0xc0046686'),
            ],
            verbose=False,
            is_nlmsg=False,
        )

        self.assertEqual(
            defines,
            {0x1278: 'BLKIOMIN', 0x6686: 'FS_IOC_MEASURE_VERITY'},
        )


class ParseMacrosTest(unittest.TestCase):
    def test_rules(self):
        macros = parse_macros_bodies(
            ('r_dir_file', 'allow $1 $2:dir search;\nallow $1 $2:file read;'),
        )

        self.assertEqual(
            macros,
            [
                MacroVariant(
                    'r_dir_file',
                    [
                        allow('$1', '$2', 'dir', ['search']),
                        allow('$1', '$2', 'file', ['read']),
                    ],
                ),
            ],
        )

    def test_skips_invalid(self):
        macros = parse_macros_bodies(
            ('broken', 'allow $1;'),
            ('valid', 'attribute $1;'),
        )

        self.assertEqual(
            macros,
            [MacroVariant('valid', [Rule(RuleType.ATTRIBUTE, ('$1',))])],
        )

    def test_skips_duplicate_rules(self):
        macros = parse_macros_bodies(
            ('first', 'attribute $1;'),
            ('second', 'attribute $1;'),
        )

        self.assertEqual([m.name for m in macros], ['first'])

    def test_arg_ifelse_variants(self):
        macros = parse_macros_bodies(
            (
                'domain_trans',
                """
allow $1 $3:process transition;
ARG_IFELSE $1 init

ARG_ELSE
allow $3 $1:process sigchld;
ARG_END
""",
            ),
        )

        self.assertEqual(
            macros,
            [
                MacroVariant(
                    'domain_trans',
                    [allow('$1', '$3', 'process', ['transition'])],
                    (ArgCondition(1, 'init', True),),
                ),
                MacroVariant(
                    'domain_trans',
                    [
                        allow('$1', '$3', 'process', ['transition']),
                        allow('$3', '$1', 'process', ['sigchld']),
                    ],
                    (ArgCondition(1, 'init', False),),
                ),
            ],
        )


class MacroBodyVariantsTest(unittest.TestCase):
    def test_without_conditions(self):
        self.assertEqual(
            macro_body_variants('allow $1 $2:file read;'),
            [('allow $1 $2:file read;', ())],
        )

    def test_branches(self):
        self.assertEqual(
            macro_body_variants(
                'a;\nARG_IFELSE $2 init\nb;\nARG_ELSE\nc;\nARG_END\nd;'
            ),
            [
                ('a;\nb;\nd;', (ArgCondition(2, 'init', True),)),
                ('a;\nc;\nd;', (ArgCondition(2, 'init', False),)),
            ],
        )

    def test_derived_argument_takes_else_branch(self):
        self.assertEqual(
            macro_body_variants(
                'ARG_IFELSE $1_exec init\nb;\nARG_ELSE\nc;\nARG_END'
            ),
            [('c;', ())],
        )

    def test_drops_contradictory_variants(self):
        body = (
            'ARG_IFELSE $1 init\na;\nARG_ELSE\nb;\nARG_END\n'
            'ARG_IFELSE $1 vendor_init\nc;\nARG_ELSE\nd;\nARG_END'
        )

        self.assertEqual(
            macro_body_variants(body),
            [
                (
                    'a;\nd;',
                    (
                        ArgCondition(1, 'init', True),
                        ArgCondition(1, 'vendor_init', False),
                    ),
                ),
                (
                    'b;\nc;',
                    (
                        ArgCondition(1, 'init', False),
                        ArgCondition(1, 'vendor_init', True),
                    ),
                ),
                (
                    'b;\nd;',
                    (
                        ArgCondition(1, 'init', False),
                        ArgCondition(1, 'vendor_init', False),
                    ),
                ),
            ],
        )


if __name__ == '__main__':
    unittest.main()

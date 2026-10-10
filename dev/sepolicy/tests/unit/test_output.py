# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import unittest

from sepolicy.output import (
    domain_file_name,
    extract_domain_type,
    group_rules,
    render_grouped_rules,
)
from sepolicy.rule_container import LineMark, RuleContainer
from sepolicy.source_macros import SourceMacros
from sepolicy.tests.helpers import R_DIR_PERMS, parse_te

MACROS = SourceMacros(
    class_perms={'dir': [('r_dir_perms', R_DIR_PERMS)]},
    class_sets=[('file_class_set', {'file', 'lnk_file'})],
    ioctls=[],
    nlmsgs=[],
    ioctl_defines={},
    nlmsg_defines={},
    macros_name_rules=[],
)


def grouped_strs(rules: RuleContainer):
    return {
        name: sorted(str(r) for r in group)
        for name, group in group_rules(rules).items()
    }


class DomainFileNameTest(unittest.TestCase):
    def test_strips_affixes(self):
        self.assertEqual(
            extract_domain_type('vendor_hal_foo_default'), 'hal_foo'
        )
        self.assertEqual(extract_domain_type('hal_foo_server'), 'hal_foo')
        self.assertEqual(extract_domain_type('foo_exec'), 'foo')

    def test_file_name(self):
        self.assertEqual(domain_file_name('hal_foo_default'), 'hal_foo.te')
        self.assertEqual(domain_file_name(None), 'leftover.te')


class GroupRulesTest(unittest.TestCase):
    def test_domain_rules(self):
        rules = parse_te(
            """
type hal_foo_default, domain;
allow hal_foo_default foo_data_file:file read;
"""
        )

        self.assertEqual(
            grouped_strs(rules),
            {
                'hal_foo.te': [
                    'allow hal_foo_default foo_data_file:file read;',
                    'type hal_foo_default, domain;',
                ],
            },
        )

    def test_simple_declarations(self):
        rules = parse_te(
            """
type foo_device, dev_type;
type foo_data_file, file_type, data_file_type;
type vendor_foo_prop, property_type;
type foo_service, service_manager_type;
type foo_hwservice, hwservice_manager_type;
attribute foo_attr;
"""
        )

        self.assertEqual(
            grouped_strs(rules),
            {
                'attributes': ['attribute foo_attr;'],
                'device.te': ['type foo_device, dev_type;'],
                'file.te': ['type foo_data_file, data_file_type, file_type;'],
                'hwservice.te': ['type foo_hwservice, hwservice_manager_type;'],
                'property.te': ['type vendor_foo_prop, property_type;'],
                'service.te': ['type foo_service, service_manager_type;'],
            },
        )

    def test_file_from_marks(self):
        rules = RuleContainer()
        for rule in parse_te(
            """
type foo, domain;
allow foo data_file:file read;
"""
        ):
            rules.add(rule, [LineMark('device/google/foo/sepolicy/bar.te', 1)])

        self.assertEqual(list(grouped_strs(rules)), ['bar.te'])

    def test_guarded_attribute_stays_separate(self):
        rules = parse_te('type app, domain, appdomain;')
        guarded = next(r for r in rules if r.parts == ('app', 'appdomain'))

        groups = group_rules(rules, {guarded: 'not_recovery'})

        self.assertEqual(
            sorted(str(r) for group in groups.values() for r in group),
            ['type app, domain;', 'typeattribute app appdomain;'],
        )


class RenderGroupedRulesTest(unittest.TestCase):
    def test_render(self):
        rules = parse_te(
            """
type hal_foo_default, domain;
type hal_foo_default_exec, exec_type, file_type;
allow hal_foo_default foo_data_file:dir { search getattr open read ioctl lock watch watch_reads };
allow hal_foo_default foo_data_file:{ file lnk_file } read;
allow hal_foo_default foo_device:chr_file { read write };
dontaudit hal_foo_default foo_device:chr_file ioctl;
"""
        )
        guarded = next(
            r
            for r in rules
            if r.parts[1:] == ('foo_device', 'chr_file')
            and r.rule_type == 'allow'
        )

        rendered = render_grouped_rules(
            group_rules(rules),
            MACROS,
            rule_guard={guarded: 'not_recovery'},
        )

        self.assertEqual(
            rendered,
            {
                'hal_foo.te': (
                    'type hal_foo_default, domain;\n'
                    'type hal_foo_default_exec, exec_type, file_type;\n'
                    '\n'
                    'allow hal_foo_default foo_data_file:dir r_dir_perms;\n'
                    'allow hal_foo_default foo_data_file:file_class_set '
                    'read;\n'
                    '\n'
                    'dontaudit hal_foo_default foo_device:chr_file ioctl;\n'
                    '\n'
                    'not_recovery(`\n'
                    'allow hal_foo_default foo_device:chr_file '
                    '{ read write };\n'
                    "')\n"
                ),
            },
        )

    def test_without_macros(self):
        rules = parse_te(
            'allow hal_foo_default foo_data_file:dir '
            '{ search getattr open read ioctl lock watch watch_reads };'
        )

        rendered = render_grouped_rules(group_rules(rules), None)

        self.assertEqual(
            rendered,
            {
                'hal_foo.te': (
                    'allow hal_foo_default foo_data_file:dir '
                    '{ getattr ioctl lock open read search watch '
                    'watch_reads };\n'
                ),
            },
        )


if __name__ == '__main__':
    unittest.main()

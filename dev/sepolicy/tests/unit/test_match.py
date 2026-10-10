# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout

from sepolicy.class_set import ClassSet
from sepolicy.match import (
    discard_rule_matches,
    match_macros_rules,
    merge_class_sets,
    merge_typeattribute_rules,
    replace_macro_rules,
    select_macros_by_group,
)
from sepolicy.rule import Rule, RuleType
from sepolicy.rule_container import LineMark, RuleContainer
from sepolicy.tests.helpers import (
    allow,
    member,
    parse_macros_bodies,
    parse_te,
)
from sepolicy.varargs import Ioctls, Types

USERFAULTFD_USE = (
    'userfaultfd_use',
    """
type $1_userfaultfd;
type_transition $1 $1:anon_inode $1_userfaultfd "[userfaultfd]";
allow $1 $1_userfaultfd:anon_inode { create ioctl read };
neverallow { domain -$1 } $1_userfaultfd:anon_inode *;
""",
)

BINDER_CALL = (
    'binder_call',
    """
allow $1 $2:binder { call transfer };
allow $2 $1:binder transfer;
allow $1 $2:fd use;
""",
)

APP_TE = """
type app, domain;
type app_userfaultfd;
type_transition app app:anon_inode app_userfaultfd "[userfaultfd]";
allow app app_userfaultfd:anon_inode { create ioctl read };
neverallow { domain -app } app_userfaultfd:anon_inode *;
allow app system_server:binder { call transfer };
allow system_server app:binder transfer;
allow app system_server:fd use;
allow app data_file:file read;
"""


def match(rules: RuleContainer, *macros: tuple[str, str]):
    return match_macros_rules(
        rules,
        parse_macros_bodies(*macros),
        verbose=False,
    )


def quiet(fn, *args):
    with redirect_stdout(io.StringIO()):
        return fn(*args)


class MatchMacrosRulesTest(unittest.TestCase):
    def test_derived_names(self):
        rules = parse_te(APP_TE)

        matches = match(rules, USERFAULTFD_USE)

        self.assertEqual([str(m) for m in matches], ['userfaultfd_use(app)'])
        self.assertEqual(len(matches[0].rules), 4)

    def test_two_args(self):
        rules = parse_te(APP_TE)

        matches = match(rules, BINDER_CALL)

        self.assertEqual(
            [str(m) for m in matches],
            ['binder_call(app, system_server)'],
        )

    def test_missing_rule(self):
        rules = parse_te(APP_TE)
        rules.remove(allow('system_server', 'app', 'binder', ['transfer']))

        self.assertEqual(match(rules, BINDER_CALL), [])

    def test_conditional_type_argument(self):
        rules = parse_te(APP_TE)
        rules.remove(
            next(r for r in rules if r.rule_type == RuleType.NEVERALLOW)
        )
        rules.add_many(
            parse_te(
                'neverallow { domain -kernel } app_userfaultfd:anon_inode *;'
            )
        )

        self.assertEqual(match(rules, USERFAULTFD_USE), [])


DOMAIN_TRANS = (
    'domain_trans',
    """
allow $1 $2:file execute;
allow $1 $3:process transition;
ARG_IFELSE $1 init

ARG_ELSE
allow $3 $1:process sigchld;
ARG_END
""",
)


class ArgConditionTest(unittest.TestCase):
    def test_not_equal_variant(self):
        rules = parse_te(
            """
allow shell foo_exec:file execute;
allow shell foo:process transition;
allow foo shell:process sigchld;
"""
        )

        matches = match(rules, DOMAIN_TRANS)

        self.assertEqual(
            [str(m) for m in matches],
            ['domain_trans(shell, foo_exec, foo)'],
        )
        self.assertEqual(len(matches[0].rules), 3)

    def test_equal_variant(self):
        rules = parse_te(
            """
allow init foo_exec:file execute;
allow init foo:process transition;
"""
        )

        matches = match(rules, DOMAIN_TRANS)

        self.assertEqual(
            [str(m) for m in matches],
            ['domain_trans(init, foo_exec, foo)'],
        )

    def test_equal_variant_leaves_extra_rule(self):
        rules = parse_te(
            """
allow init foo_exec:file execute;
allow init foo:process transition;
allow foo init:process sigchld;
"""
        )

        matches = match(rules, DOMAIN_TRANS)

        self.assertEqual(
            [(str(m), len(m.rules)) for m in matches],
            [('domain_trans(init, foo_exec, foo)', 2)],
        )

    def test_not_equal_variant_requires_conditional_rule(self):
        rules = parse_te(
            """
allow shell foo_exec:file execute;
allow shell foo:process transition;
"""
        )

        self.assertEqual(match(rules, DOMAIN_TRANS), [])


SET_XPERM_FILTER = (
    'set_xperm_filter',
    """
allowxperm appdomain $1:chr_file ioctl { $3 };
neverallowxperm { appdomain -$2 } $1:chr_file ioctl { $4 };
allowxperm $2 $1:chr_file ioctl { $4 };
""",
)


class VarargsArgumentTest(unittest.TestCase):
    def test_binds_ioctls(self):
        rules = parse_te(
            """
allowxperm appdomain gpu_device:chr_file ioctl { 0x1 0x5-0x6 };
neverallowxperm { appdomain -mali_target_sdk } gpu_device:chr_file ioctl 0x9;
allowxperm mali_target_sdk gpu_device:chr_file ioctl 0x9;
"""
        )

        matches = match(rules, SET_XPERM_FILTER)

        self.assertEqual(
            [m.macro.parts for m in matches],
            [
                (
                    'gpu_device',
                    'mali_target_sdk',
                    Ioctls([(0x1, 0x1), (0x5, 0x6)]),
                    Ioctls([(0x9, 0x9)]),
                ),
            ],
        )

    def test_reused_argument_must_match(self):
        rules = parse_te(
            """
allowxperm appdomain gpu_device:chr_file ioctl 0x1;
neverallowxperm { appdomain -mali_target_sdk } gpu_device:chr_file ioctl 0x9;
allowxperm mali_target_sdk gpu_device:chr_file ioctl 0xa;
"""
        )

        self.assertEqual(match(rules, SET_XPERM_FILTER), [])


class DiscardRuleMatchesTest(unittest.TestCase):
    def test_discards_subset(self):
        rules = parse_te(APP_TE)
        binder_call_only = (
            'binder_call_only',
            'allow $1 $2:binder { call transfer };',
        )

        matches = match(rules, binder_call_only, BINDER_CALL)
        kept = quiet(discard_rule_matches, matches, False)

        self.assertEqual(
            [str(m) for m in kept],
            ['binder_call(app, system_server)'],
        )

    def test_equal_rules_prefer_fewer_args(self):
        rules = parse_te('allow app app:binder call;')
        self_call = ('self_call', 'allow $1 $1:binder call;')
        pair_call = ('pair_call', 'allow $1 $2:binder call;')

        matches = match(rules, self_call, pair_call)
        kept = quiet(discard_rule_matches, matches, False)

        self.assertEqual([str(m) for m in kept], ['self_call(app)'])


class ReplaceMacroRulesTest(unittest.TestCase):
    def test_replaces_rules_and_keeps_common_marks(self):
        rules = RuleContainer()
        binder_rules = parse_te(
            """
allow app system_server:binder { call transfer };
allow system_server app:binder transfer;
allow app system_server:fd use;
"""
        )
        mark = LineMark('app.te', 3)
        other_mark = LineMark('app.te', 9)
        for i, rule in enumerate(binder_rules):
            marks = [mark, other_mark] if i == 0 else [mark]
            rules.add(rule, marks)
        unrelated = allow('app', 'data_file', 'file', ['read'])
        rules.add(unrelated)

        matches = match(rules, BINDER_CALL)
        quiet(replace_macro_rules, rules, matches, 'test', False)

        macro = matches[0].macro
        self.assertEqual(set(rules), {macro, unrelated})
        self.assertEqual(rules.marks(macro), {mark})


class SelectMacrosByGroupTest(unittest.TestCase):
    def test_drops_match_spanning_unrelated_lines(self):
        rules = RuleContainer()
        for i, rule in enumerate(parse_te(APP_TE)):
            rules.add(rule, [LineMark('app.te', i)])

        matches = match(rules, BINDER_CALL)
        kept = quiet(
            select_macros_by_group,
            matches,
            rules,
            RuleContainer(),
            False,
        )

        self.assertEqual(kept, [])

    def test_keeps_match_from_single_line(self):
        rules = RuleContainer()
        mark = LineMark('app.te', 1)
        for rule in parse_te(APP_TE):
            rules.add(rule, [mark])

        matches = match(rules, BINDER_CALL)
        kept = quiet(
            select_macros_by_group,
            matches,
            rules,
            RuleContainer(),
            False,
        )

        self.assertEqual(kept, matches)

    def test_ignores_reference_rules(self):
        rules = RuleContainer()
        reference = RuleContainer()
        for i, rule in enumerate(parse_te(APP_TE)):
            rules.add(rule, [LineMark('app.te', i)])
            if rule.rule_type == RuleType.ALLOW and rule.parts[2] != 'fd':
                reference.add(rule)

        matches = match(rules, BINDER_CALL)
        kept = quiet(select_macros_by_group, matches, rules, reference, False)

        self.assertEqual(kept, matches)


class MergeTypeattributeRulesTest(unittest.TestCase):
    def test_merges_attributes(self):
        rules = parse_te('type app, domain, appdomain;')

        merge_typeattribute_rules(rules)

        self.assertEqual(
            set(rules),
            {Rule(RuleType.TYPE, ('app',), Types({'domain', 'appdomain'}))},
        )

    def test_keeps_guarded_attribute(self):
        rules = parse_te('type app, domain, appdomain;')
        guarded = member('app', 'appdomain')

        merge_typeattribute_rules(rules, {guarded: 'not_recovery'})

        self.assertEqual(
            set(rules),
            {
                Rule(RuleType.TYPE, ('app',), Types({'domain'})),
                guarded,
            },
        )

    def test_all_attributes_guarded(self):
        rules = parse_te('type app, domain;')
        guarded = member('app', 'domain')

        merge_typeattribute_rules(rules, {guarded: 'not_recovery'})

        self.assertEqual(
            set(rules),
            {Rule(RuleType.TYPE, ('app',), Types(())), guarded},
        )

    def test_attribute_of_undeclared_type(self):
        rules = parse_te('typeattribute app domain;')

        merge_typeattribute_rules(rules)

        self.assertEqual(set(rules), {member('app', 'domain')})


class MergeClassSetsTest(unittest.TestCase):
    def test_merges_named_class_set(self):
        rules = parse_te('allow app data_file:{ file lnk_file dir } read;')
        class_sets = [('file_class_set', {'file', 'lnk_file'})]

        merge_class_sets(rules, class_sets)

        self.assertEqual(
            [str(r) for r in rules],
            ['allow app data_file:{ dir file_class_set } read;'],
        )
        rule = next(iter(rules))
        self.assertIsInstance(rule.parts[2], ClassSet)

    def test_single_class_is_kept(self):
        rules = parse_te('allow app data_file:file read;')

        merge_class_sets(rules, [('file_class_set', {'file', 'lnk_file'})])

        self.assertEqual(
            set(rules),
            {allow('app', 'data_file', 'file', ['read'])},
        )

    def test_different_perms_are_not_merged(self):
        rules = parse_te(
            """
allow app data_file:file read;
allow app data_file:lnk_file getattr;
"""
        )
        before = set(rules)

        merge_class_sets(rules, [('file_class_set', {'file', 'lnk_file'})])

        self.assertEqual(set(rules), before)

    def test_requires_common_source_line(self):
        rules = parse_te('allow app data_file:{ file lnk_file } read;')
        mark_source = RuleContainer()
        for i, rule in enumerate(rules):
            mark_source.add(rule, [LineMark('app.te', i)])
        before = set(rules)

        merge_class_sets(
            rules,
            [('file_class_set', {'file', 'lnk_file'})],
            mark_source,
        )

        self.assertEqual(set(rules), before)


if __name__ == '__main__':
    unittest.main()

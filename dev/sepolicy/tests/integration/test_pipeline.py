# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import io
import itertools
import unittest
from contextlib import redirect_stdout
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from sepolicy.add_policy_provider import AddPolicyProvider
from sepolicy.cleanup_policy_provider import CleanupPolicyProvider
from sepolicy.expanded_guard_policy_provider import (
    ExpandedGuardPolicyProvider,
)
from sepolicy.gather_source_text_policy_provider import (
    GatherSourceTextPolicyProvider,
)
from sepolicy.hardcoded_policy_provider import HardcodedPolicyProvider
from sepolicy.macro import MacroVariant
from sepolicy.macro_match_policy_provider import MacroMatchPolicyProvider
from sepolicy.macro_replace_policy_provider import MacroReplacePolicyProvider
from sepolicy.policy import (
    Policy,
    PolicyIndex,
    PolicyMetadata,
    PolicyOrigin,
    PolicyProvider,
    PolicyType,
    hardcoded,
)
from sepolicy.referenced_policy_provider import ReferencedPolicyProvider
from sepolicy.restore_optimized_policy_provider import (
    RestoreOptimizedPolicyProvider,
)
from sepolicy.rule import Rule
from sepolicy.rule_container import RuleContainer
from sepolicy.source_macros import SourceMacros
from sepolicy.tests.helpers import (
    R_DIR_PERMS,
    allow,
    parse_macros_bodies,
    parse_te,
)

policy_counter = itertools.count()

BINDER_CALL = (
    'binder_call',
    """
allow $1 $2:binder { call transfer };
allow $2 $1:binder transfer;
allow $1 $2:fd use;
""",
)


def unique_name(name: str):
    return f'test_{name}_{next(policy_counter)}'


def policy(name: str, *rules: Rule):
    return hardcoded(name=unique_name(name), rules=rules)


@dataclass(frozen=True)
class MacrosOrigin(PolicyOrigin):
    pass


class MacrosPolicyProvider(PolicyProvider):
    def __init__(
        self,
        class_perms: Dict[str, List[Tuple[str, Set[str]]]],
        macros_name_rules: List[MacroVariant],
    ):
        super().__init__(MacrosOrigin)

        self.__macros = SourceMacros(
            class_perms=class_perms,
            class_sets=[],
            ioctls=[],
            nlmsgs=[],
            ioctl_defines={},
            nlmsg_defines={},
            macros_name_rules=macros_name_rules,
        )

    def get_policy(
        self,
        policy_index: PolicyIndex,
        policy_type: PolicyType,
        metadata: Optional[PolicyMetadata],
    ):
        return Policy(
            policy_type,
            RuleContainer(),
            genfs_rules=RuleContainer(),
            contexts={},
            macros=self.__macros,
        )


TYPES = tuple(
    parse_te(
        """
attribute domain;
attribute appdomain;
attribute fs_type;
type app, domain, appdomain;
type kernel, domain;
type system_server, domain;
type cgroup_app, fs_type;
type rootfs, fs_type;
"""
    )
)

OPTIMIZED_RECOVERY = (
    *TYPES,
    allow('domain', 'fs_type', 'dir', ['getattr']),
    allow('domain', 'rootfs', 'dir', ['search']),
    allow(
        'appdomain',
        'cgroup_app',
        'dir',
        ['ioctl', 'lock', 'open', 'read', 'search', 'watch', 'watch_reads'],
    ),
    allow(
        'kernel',
        'rootfs',
        'dir',
        ['ioctl', 'lock', 'open', 'read', 'watch', 'watch_reads'],
    ),
)


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.index = PolicyIndex()
        self.index.register(HardcodedPolicyProvider())
        self.index.register(CleanupPolicyProvider())
        self.index.register(ExpandedGuardPolicyProvider(verbose=False))
        self.index.register(RestoreOptimizedPolicyProvider())
        self.index.register(MacroMatchPolicyProvider(verbose=False))
        self.index.register(MacroReplacePolicyProvider(verbose=False))
        self.index.register(AddPolicyProvider())
        self.index.register(ReferencedPolicyProvider())
        self.index.register(GatherSourceTextPolicyProvider(verbose=False))
        self.index.register(
            MacrosPolicyProvider(
                {'dir': [('r_dir_perms', R_DIR_PERMS)]},
                parse_macros_bodies(BINDER_CALL),
            )
        )
        self.macros = PolicyType(unique_name('macros'), MacrosOrigin())

    def get(self, policy_type: PolicyType):
        with redirect_stdout(io.StringIO()):
            return self.index.get(policy_type)

    def test_guard_skips_rule_present_through_broader_rule(self):
        present = allow('appdomain', 'cgroup_app', 'dir', R_DIR_PERMS)
        absent = allow('appdomain', 'rootfs', 'dir', ['write'])
        source = policy('source', present, absent)

        guarded = self.get(
            source.expanded_guard(
                expander=policy('expander', *TYPES),
                reference=policy('recovery', *OPTIMIZED_RECOVERY),
                guard='not_recovery',
            )
        )

        self.assertEqual(guarded.guarded_rules, {absent: 'not_recovery'})

    def test_recovery_only(self):
        reference = policy(
            'reference',
            *TYPES,
            allow('domain', 'fs_type', 'dir', ['getattr']),
            allow('domain', 'rootfs', 'dir', ['search']),
            allow('appdomain', 'cgroup_app', 'dir', R_DIR_PERMS),
        )
        recovery = policy('recovery', *OPTIMIZED_RECOVERY)

        recovery_only = self.get(
            recovery.cleanup(covered=(reference,)).restore_optimized(
                macros=self.macros,
                reference=recovery,
            )
        )

        self.assertEqual(
            set(recovery_only.rules),
            {allow('kernel', 'rootfs', 'dir', R_DIR_PERMS)},
        )

    def test_macro_match_and_replace(self):
        unrelated = allow('app', 'rootfs', 'dir', ['search'])
        source = policy(
            'source',
            *parse_te(
                """
allow app system_server:binder { call transfer };
allow system_server app:binder transfer;
allow app system_server:fd use;
"""
            ),
            unrelated,
        )

        replaced = self.get(
            source.macro_match(macros=self.macros).macro_replace()
        )

        self.assertEqual(
            sorted(str(r) for r in replaced.rules),
            [
                'allow app rootfs:dir search;',
                'binder_call(app, system_server)',
            ],
        )

    def test_guard_carries_over_to_macro(self):
        binder_rules = tuple(
            parse_te(
                """
allow app system_server:binder { call transfer };
allow system_server app:binder transfer;
allow app system_server:fd use;
"""
            )
        )
        present = allow('app', 'rootfs', 'dir', ['search'])
        source = policy('source', *binder_rules, present)
        recovery = policy('recovery', *TYPES, present)

        replaced = self.get(
            source.macro_match(macros=self.macros)
            .expanded_guard(
                expander=policy('expander', *TYPES),
                reference=recovery,
                guard='not_recovery',
            )
            .macro_replace()
        )

        guarded = {str(r): g for r, g in replaced.guarded_rules.items()}
        self.assertEqual(
            guarded,
            {'binder_call(app, system_server)': 'not_recovery'},
        )

    def test_public_private(self):
        public_rule = allow('app', 'rootfs', 'dir', ['search'])
        private_rule = allow('app', 'cgroup_app', 'dir', ['search'])
        source = policy('source', public_rule, private_rule)
        reference = policy('reference', public_rule)

        public = self.get(source.public(reference=reference))
        private = self.get(source.private(reference=reference))

        self.assertEqual(set(public.rules), {public_rule})
        self.assertEqual(set(private.rules), {private_rule})

    def test_add_with_guard(self):
        rule = allow('app', 'rootfs', 'dir', ['search'])
        added_rule = allow('recovery', 'rootfs', 'dir', ['search'])
        source = policy('source', rule)

        added = self.get(
            source.add(
                added=policy('added', added_rule),
                guard='recovery_only',
            )
        )

        self.assertEqual(set(added.rules), {rule, added_rule})
        self.assertEqual(added.guarded_rules, {added_rule: 'recovery_only'})

    def test_gather_source_text(self):
        source = policy(
            'source',
            *parse_te(
                """
type hal_foo_default, domain;
allow hal_foo_default rootfs:dir search;
"""
            ),
        )

        gathered = self.get(source.gather_source_text())

        assert gathered.source_text is not None
        self.assertEqual(
            {p.name: t for p, t in gathered.source_text.texts.items()},
            {
                'hal_foo.te': (
                    'type hal_foo_default, domain;\n'
                    '\n'
                    'allow hal_foo_default rootfs:dir search;\n'
                ),
            },
        )


if __name__ == '__main__':
    unittest.main()

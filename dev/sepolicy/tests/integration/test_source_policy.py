# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import io
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from typing import Dict, List

from utils.utils import android_root

SYSTEM_SEPOLICY = Path(android_root, 'system/sepolicy')
TOOLS_DIR = Path(android_root, 'out/host/linux-x86/bin')

if not SYSTEM_SEPOLICY.is_dir():
    raise unittest.SkipTest(f'{SYSTEM_SEPOLICY} not found')

if not all(Path(TOOLS_DIR, t).exists() for t in ('checkpolicy', 'secilc')):
    raise unittest.SkipTest(f'checkpolicy, secilc not built in {TOOLS_DIR}')

if shutil.which('m4') is None:
    raise unittest.SkipTest('m4 not found')

from sepolicy.cil_policy import parse_dump_policy_variables
from sepolicy.conditional_type import ConditionalType
from sepolicy.macro import MacroVariant
from sepolicy.match import match_macros_rules
from sepolicy.policy import (
    PolicyIndex,
    PolicyMetadata,
    source_platform_public,
)
from sepolicy.rule import Rule, rule_part
from sepolicy.rule_container import RuleContainer
from sepolicy.source_te_policy_provider import SourceTePolicyProvider
from sepolicy.tests.helpers import R_DIR_PERMS, VERSION, write_fake_dump
from sepolicy.varargs import TypeTransitionTag


def substitute(rule: Rule, args: Dict[str, str]) -> Rule:
    def sub_str(value: str):
        for arg, replacement in args.items():
            value = value.replace(arg, replacement)

        return value

    def sub(value: rule_part):
        if isinstance(value, ConditionalType):
            return ConditionalType(
                [sub_str(v) for v in value.positive],
                [sub_str(v) for v in value.negative],
                value.is_all,
            )

        if isinstance(value, str):
            return sub_str(value)

        return value

    return Rule(
        rule.rule_type,
        tuple(sub(p) for p in rule.parts),
        rule.varargs,
    )


class SourcePolicyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as dump_dir:
            write_fake_dump(Path(dump_dir))
            variables = parse_dump_policy_variables(Path(dump_dir), VERSION)

        metadata = PolicyMetadata(VERSION, variables)

        index = PolicyIndex()
        index.register(
            SourceTePolicyProvider(
                extra_rules_paths={},
                extra_macros_paths={},
                current=True,
                verbose=False,
            )
        )

        with redirect_stdout(io.StringIO()):
            cls.policy = index.get(source_platform_public, metadata)

        assert cls.policy.macros is not None
        cls.macros = cls.policy.macros
        cls.variants: Dict[str, List[MacroVariant]] = {}
        for variant in cls.macros.macros_name_rules:
            cls.variants.setdefault(variant.name, []).append(variant)

    def variant_rules(self, name: str, args: Dict[str, str]):
        for variant in self.variants[name]:
            if all(
                (args.get(f'${c.arg_index}') == c.value) == c.equal
                for c in variant.conditions
            ):
                return variant.rules

        assert False, name

    def test_perm_macros(self):
        self.assertIn(
            ('r_dir_perms', R_DIR_PERMS), self.macros.class_perms['dir']
        )

    def test_ioctl_defines(self):
        self.assertEqual(self.macros.ioctl_defines[0x1278], 'BLKIOMIN')

    def test_app_domain_blocks_io_uring(self):
        self.assertIn(
            Rule(
                'type_transition',
                ('$1', '$1', 'anon_inode', '$1_block_io_uring'),
                TypeTransitionTag('"[io_uring]"'),
            ),
            self.variant_rules('app_domain', {}),
        )

    def test_macros_match_their_expansion(self):
        for name, args in (
            ('app_domain', {'$1': 'foo_app'}),
            ('userfaultfd_use', {'$1': 'foo_app'}),
            ('binder_call', {'$1': 'foo_app', '$2': 'foo_service'}),
            ('init_daemon_domain', {'$1': 'foo_daemon'}),
        ):
            with self.subTest(macro=name, args=args):
                rules = RuleContainer(
                    substitute(r, args) for r in self.variant_rules(name, args)
                )

                matches = match_macros_rules(
                    rules,
                    self.variants[name],
                    verbose=False,
                )

                self.assertEqual(
                    [m.macro.parts for m in matches],
                    [tuple(args.values())],
                )

    def test_policy_rules(self):
        self.assertIn(Rule('attribute', ('domain',)), self.policy.rules)


if __name__ == '__main__':
    unittest.main()

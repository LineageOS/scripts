# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import io
import itertools
import tempfile
import unittest
from contextlib import redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

from utils.frozendict import FrozenDict
from utils.utils import android_root, run_cmd

TOOLS = ('checkpolicy', 'secilc')
TOOLS_DIR = Path(android_root, 'out/host/linux-x86/bin')

if not all(Path(TOOLS_DIR, tool).exists() for tool in TOOLS):
    raise unittest.SkipTest(f'{", ".join(TOOLS)} not built in {TOOLS_DIR}')

from sepolicy.binary_compiled_policy_provider import (
    BinaryCompiledPolicyProvider,
)
from sepolicy.cil_policy import SEPOLICY_FLAGGING_BP_PATH, parse_cil_lines
from sepolicy.cleanup_policy_provider import remove_covered_rules
from sepolicy.compile_utils import (
    binary_to_cil_policy,
    cil_to_binary_policy,
    secilc_path,
    source_to_cil_policy,
)
from sepolicy.compiled_policy_provider import CompiledPolicyProvider
from sepolicy.dump_binary_policy_provider import DumpBinaryPolicyProvider
from sepolicy.expander import EXPAND_TYPES, Coverage
from sepolicy.policy import (
    Policy,
    PolicyIndex,
    PolicyMetadata,
    PolicyOrigin,
    PolicyProvider,
    PolicyType,
    binary_compiled,
    compiled,
    recovery,
)
from sepolicy.restore_optimized_policy_provider import (
    restore_optimized_rule,
)
from sepolicy.rule import Rule, RuleType
from sepolicy.rule_container import RuleContainer
from sepolicy.tests.helpers import R_FILE_PERMS, allow, write_fake_dump
from sepolicy.varargs import Types, TypeTransitionTag

POLICY_HEAD = """\
class process
class file
class dir
class anon_inode

sid kernel

common file { ioctl read write create getattr setattr lock open map watch \
watch_reads search add_name remove_name }

class process { transition fork }
class file inherits file
class dir inherits file
class anon_inode inherits file

sensitivity s0;
dominance { s0 }
category c0;
level s0:c0;

mlsconstrain process transition ( l1 eq l2 );

"""

OPTIMIZABLE_BODY = [
    'attribute domain;',
    'attribute appdomain;',
    'attribute file_type;',
    'type kernel, domain;',
    'type app, domain, appdomain;',
    'type data_file, file_type;',
    'allow domain file_type:file { read getattr open };',
    (
        'allow appdomain data_file:file '
        '{ read getattr open ioctl lock map watch watch_reads };'
    ),
]
OPTIMIZABLE_TYPES = ['kernel', 'app', 'data_file']

UNOPTIMIZED = allow('appdomain', 'data_file', 'file', R_FILE_PERMS)
OPTIMIZED = allow(
    'appdomain',
    'data_file',
    'file',
    ['ioctl', 'lock', 'map', 'watch', 'watch_reads'],
)

METADATA = PolicyMetadata('202604', FrozenDict({}))

policy_counter = itertools.count()


def policy_conf(body: Iterable[str], types: Iterable[str]):
    types_str = ' '.join(types)
    return (
        POLICY_HEAD
        + '\n'.join(body)
        + f"""

role r;
role r types {{ {types_str} }};

user u roles {{ r }} level s0 range s0 - s0:c0;

sid kernel u:r:kernel:s0
"""
    )


def parse_cil(cil_path: Path):
    rules = RuleContainer()
    parse_cil_lines(
        cil_path,
        rules,
        RuleContainer(),
        {},
        reference_conditional_types_maps=[],
        classmap=None,
        version='202604',
        name='test',
        verbose=False,
    )
    return rules


def access_rules(rules: Iterable[Rule]) -> List[Rule]:
    return [r for r in rules if r.rule_type in EXPAND_TYPES]


def compile_optimized_binary(cil_path: Path, binary_path: Path):
    run_cmd(
        [
            str(secilc_path),
            '-m',
            '-M',
            'true',
            '-G',
            '-O',
            '-c',
            '30',
            '-N',
            str(cil_path),
            '-o',
            str(binary_path),
            '-f',
            '/dev/null',
        ]
    )


@dataclass(frozen=True)
class TextOrigin(PolicyOrigin):
    pass


class TextPolicyProvider(PolicyProvider):
    def __init__(self, text: str):
        super().__init__(TextOrigin)

        self.__text = text

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
            metadata=metadata,
            text=self.__text,
        )


class ToolsTest(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.temp_path = Path(temp_dir.name)

    def compile_cil(self, body: Iterable[str], types: Iterable[str]):
        conf_path = Path(self.temp_path, 'policy.conf')
        conf_path.write_text(policy_conf(body, types))

        cil_path = Path(self.temp_path, 'policy.cil')
        with source_to_cil_policy(conf_path) as compiled_path:
            cil_path.write_text(compiled_path.read_text())

        return cil_path

    def decompile_binary(self, binary_path: Path):
        with binary_to_cil_policy(binary_path) as cil_path:
            return parse_cil(cil_path)

    def test_formatted_rules_compile(self):
        type_transition = Rule(
            RuleType.TYPE_TRANSITION,
            ('app', 'app', 'anon_inode', 'app_block_io_uring'),
            TypeTransitionTag('"[io_uring]"'),
        )

        cil_path = self.compile_cil(
            [
                'attribute domain;',
                'type kernel, domain;',
                'type app, domain;',
                str(Rule(RuleType.TYPE, ('app_block_io_uring',), Types(()))),
                str(type_transition),
            ],
            ['kernel', 'app', 'app_block_io_uring'],
        )

        self.assertIn(type_transition, parse_cil(cil_path))

    def test_optimized_recovery(self):
        cil_path = self.compile_cil(OPTIMIZABLE_BODY, OPTIMIZABLE_TYPES)

        with cil_to_binary_policy(cil_path) as binary_path:
            reference = self.decompile_binary(binary_path)

        optimized_path = Path(self.temp_path, 'optimized')
        compile_optimized_binary(cil_path, optimized_path)
        recovery_rules = self.decompile_binary(optimized_path)

        self.assertIn(UNOPTIMIZED, reference)
        self.assertIn(OPTIMIZED, recovery_rules)
        self.assertNotIn(OPTIMIZED, reference)

        self.assertEqual(
            access_rules(remove_covered_rules(recovery_rules, reference)),
            [],
        )

        self.assertEqual(
            restore_optimized_rule(
                OPTIMIZED,
                Coverage(recovery_rules),
                {'file': [('r_file_perms', R_FILE_PERMS)]},
            ),
            UNOPTIMIZED,
        )

    def test_compiled_providers(self):
        index = PolicyIndex()
        index.register(
            TextPolicyProvider(
                policy_conf(OPTIMIZABLE_BODY, OPTIMIZABLE_TYPES),
            )
        )
        index.register(CompiledPolicyProvider(verbose=False))
        index.register(BinaryCompiledPolicyProvider(verbose=False))

        name = f'test_compiled_{next(policy_counter)}'
        text = PolicyType(name, TextOrigin())
        compiled_type = compiled(name=name, source=text)
        binary_type = binary_compiled(
            name=f'{name}_binary',
            source=compiled_type,
        )

        compiled_policy = index.get(compiled_type, METADATA)
        binary_policy = index.get(binary_type, METADATA)

        self.assertIn(UNOPTIMIZED, compiled_policy.rules)
        self.assertIn(UNOPTIMIZED, binary_policy.rules)
        assert compiled_policy.text is not None
        self.assertIn('(allow appdomain data_file', compiled_policy.text)

    @unittest.skipUnless(
        SEPOLICY_FLAGGING_BP_PATH.exists(),
        f'{SEPOLICY_FLAGGING_BP_PATH} not found',
    )
    def test_dump_binary(self):
        dump_root = Path(self.temp_path, 'dump')
        write_fake_dump(dump_root)
        Path(dump_root, 'recovery').mkdir()
        cil_path = self.compile_cil(OPTIMIZABLE_BODY, OPTIMIZABLE_TYPES)
        compile_optimized_binary(
            cil_path,
            Path(dump_root, 'recovery/sepolicy'),
        )

        index = PolicyIndex()
        index.register(DumpBinaryPolicyProvider(dump_root, verbose=False))
        with redirect_stdout(io.StringIO()):
            recovery_policy = index.get(recovery)

        assert recovery_policy.metadata is not None
        self.assertEqual(recovery_policy.metadata.version, '202604')
        self.assertEqual(
            recovery_policy.metadata.variables['target_recovery'],
            'true',
        )
        self.assertIn(OPTIMIZED, recovery_policy.rules)

    @unittest.skipUnless(
        SEPOLICY_FLAGGING_BP_PATH.exists(),
        f'{SEPOLICY_FLAGGING_BP_PATH} not found',
    )
    def test_dump_binary_missing(self):
        dump_root = Path(self.temp_path, 'dump')
        write_fake_dump(dump_root)

        index = PolicyIndex()
        index.register(DumpBinaryPolicyProvider(dump_root, verbose=False))

        self.assertIsNone(index.find(recovery))


if __name__ == '__main__':
    unittest.main()

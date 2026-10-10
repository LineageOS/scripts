# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import io
from contextlib import redirect_stdout
from pathlib import Path
from typing import Iterable, Optional, Tuple

from sepolicy.classmap import Classmap
from sepolicy.macro import parse_macros
from sepolicy.rule import Rule, RuleType
from sepolicy.rule_container import LineMark, RuleContainer
from sepolicy.rules import split_normalize_rules_text
from sepolicy.source_rule import SourceRuleParser
from sepolicy.varargs import Perms

FILE_PERMS = [
    'ioctl',
    'read',
    'write',
    'create',
    'getattr',
    'setattr',
    'lock',
    'relabelfrom',
    'relabelto',
    'append',
    'map',
    'unlink',
    'link',
    'rename',
    'execute',
    'open',
    'watch',
    'watch_reads',
]

CLASSMAP = Classmap(
    {
        'file': FILE_PERMS,
        'lnk_file': FILE_PERMS,
        'chr_file': FILE_PERMS,
        'anon_inode': FILE_PERMS,
        'dir': FILE_PERMS + ['add_name', 'remove_name', 'search', 'rmdir'],
        'process': ['fork', 'transition', 'sigchld', 'ptrace'],
        'binder': ['call', 'transfer', 'set_context_mgr', 'impersonate'],
        'fd': ['use'],
        'service_manager': ['add', 'find', 'list'],
    }
)

R_FILE_PERMS = {
    'getattr',
    'open',
    'read',
    'ioctl',
    'lock',
    'map',
    'watch',
    'watch_reads',
}

R_DIR_PERMS = {
    'open',
    'getattr',
    'read',
    'search',
    'ioctl',
    'lock',
    'watch',
    'watch_reads',
}


def parse_te(text: str, path: Optional[str] = None) -> RuleContainer:
    rules = RuleContainer()

    for line, rule_text in enumerate(split_normalize_rules_text(text), 1):
        marks = None
        if path is not None:
            marks = [LineMark(path, line)]

        parser = SourceRuleParser(
            lambda r, m=marks: rules.add(r, m),
            CLASSMAP,
        )
        parser.parse_line(rule_text)

    return rules


def parse_macros_bodies(*name_bodies: Tuple[str, str]):
    with redirect_stdout(io.StringIO()):
        return parse_macros(CLASSMAP, list(name_bodies))


def allow(
    src: str,
    dst: str,
    class_name: str,
    perms: Iterable[str],
    rule_type: str = RuleType.ALLOW,
):
    return Rule(rule_type, (src, dst, class_name), Perms(perms, False))


def member(t: str, attribute: str):
    return Rule(RuleType.TYPEATTRIBUTE, (t, attribute))


VERSION = '202604'


def write_fake_dump(dump_root: Path):
    for partition, props in (
        ('system', ['ro.build.type=user']),
        ('vendor', ['ro.bionic.arch=arm64', f'ro.board.api_level={VERSION}']),
    ):
        Path(dump_root, partition, 'etc').mkdir(parents=True)
        Path(dump_root, partition, 'build.prop').write_text(
            '\n'.join(props) + '\n'
        )
        Path(dump_root, partition, 'etc/build_flags.json').write_text(
            '{"flags": []}'
        )

# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from functools import partial
from itertools import chain
from pathlib import Path
from typing import List, Set

from sepolicy.classmap import Classmap
from sepolicy.rule import Rule
from sepolicy.source_rule import SourceRule
from utils.utils import Color, color_print

ALLOWED_ROOT_SYSTEM_SEPOLICY_RULES_SUBDIRS = [
    'private',
    'public',
    'vendor',
]


def resolve_rule_paths(
    rule_paths: List[Path],
    system_sepolicy_path: Path,
    verbose: bool,
):
    rule_file_paths: List[Path] = []

    for rule_path in rule_paths:
        if rule_path.is_file() and rule_path.suffix == '.te':
            if verbose:
                print(f'Loading rules: {rule_path}')
            rule_file_paths.append(rule_path)
            continue

        if not rule_path.is_dir():
            color_print(
                f'Rule path {rule_path} is not a file or directory',
                color=Color.RED,
            )
            continue

        # --current uses the root directory, which contains a lot of .te
        # files from other versions of the API too
        if rule_path == system_sepolicy_path:
            subdirs_to_scan = [
                Path(rule_path, subdir_name)
                for subdir_name in ALLOWED_ROOT_SYSTEM_SEPOLICY_RULES_SUBDIRS
            ]
        else:
            subdirs_to_scan = [rule_path]

        for file_subdir in subdirs_to_scan:
            if verbose:
                print(f'Loading rules from directory: {file_subdir}')

            for file_path in file_subdir.rglob('*.te'):
                if not file_path.is_file():
                    continue

                if verbose:
                    print(file_path.relative_to(file_subdir))
                rule_file_paths.append(file_path)

    return rule_file_paths


def split_rules(
    lines: List[str],
    ending_char: str = ';',
    only_end_at_ending_char: bool = False,
):
    open_set = set(['{', '(', '`'])
    close_set = set(['}', ')', "'"])
    level = 0
    block = ''

    pending_macro_end = False
    for line in lines:
        assert '#' not in line

        for c in line:
            if c in open_set:
                level += 1
            elif c in close_set:
                level -= 1

            # Previous macro ended with ) and this is not an ending char, start a new block
            if pending_macro_end and c != ending_char:
                pending_macro_end = False
                if not only_end_at_ending_char:
                    block = block.strip()
                    yield block
                    block = ''

            block += c

            is_macro_end = level == 0 and c == ')'
            is_rule_end = level == 0 and c == ending_char

            if is_macro_end:
                pending_macro_end = True
                continue

            # Handle macro ending with );
            if pending_macro_end and c == ending_char:
                is_macro_end = True

            if is_macro_end or is_rule_end:
                block = block.strip()
                yield block
                block = ''

    if only_end_at_ending_char and block:
        block = block.strip()
        yield block
        block = ''

    assert not block.strip(), block


def parse_rules(classmap: Classmap, rules: List[str]):
    from_line_fn = partial(SourceRule.from_line, classmap=classmap)
    decompiled_rules: List[Rule] = []
    unique_rules: Set[Rule] = set()

    for rule in list(chain.from_iterable(map(from_line_fn, rules))):
        if rule in unique_rules:
            continue

        decompiled_rules.append(rule)
        unique_rules.add(rule)

    return decompiled_rules

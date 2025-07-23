# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from functools import partial
from itertools import chain
from pathlib import Path
from typing import List, Optional, Set

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
    rule_paths: List[str],
    system_sepolicy_path: Optional[Path],
):
    rule_file_paths: List[str] = []

    for rule_path in rule_paths:
        rp = Path(rule_path)
        if rp.is_file() and rp.suffix == '.te':
            rule_file_paths.append(str(rp.resolve()))
            continue

        if not rp.is_dir():
            color_print(
                f'Rule path {rule_path} is not a file or directory',
                color=Color.RED,
            )
            continue

        # --current uses the root directory, which contains a lot of .te
        # files from other versions of the API too
        if rp == system_sepolicy_path:
            subdirs_to_scan = [
                Path(rp, subdir_name)
                for subdir_name in ALLOWED_ROOT_SYSTEM_SEPOLICY_RULES_SUBDIRS
            ]
        else:
            subdirs_to_scan = [rp]

        for subdir in subdirs_to_scan:
            for file in subdir.rglob('*.te'):
                if not file.is_file():
                    color_print(
                        f'Rule path {rule_path} is not a file',
                        color=Color.YELLOW,
                    )
                    continue

                rule_file_paths.append(str(file.resolve()))

    return rule_file_paths


def split_rules(lines: List[str]):
    open_set = set(['{', '(', '`'])
    close_set = set(['}', ')', "'"])
    level = 0
    block = ''

    last_c_macro_end = False
    for line in lines:
        assert '#' not in line

        for c in line:
            if c in open_set:
                level += 1
            elif c in close_set:
                level -= 1

            # Previous macro ended with ) and this is not a ;, start a new block
            if last_c_macro_end and c != ';':
                last_c_macro_end = False
                block = block.strip()
                yield block
                block = ''

            block += c

            is_macro_end = level == 0 and c == ')'
            is_rule_end = level == 0 and c == ';'

            if is_macro_end:
                last_c_macro_end = True
                continue

            # Handle macro ending with );
            if last_c_macro_end and c == ';':
                is_macro_end = True

            if is_macro_end or is_rule_end:
                block = block.strip()
                yield block
                block = ''

    assert not block.strip()


def decompile_rules(classmap: Classmap, rules: List[str]):
    from_line_fn = partial(SourceRule.from_line, classmap=classmap)
    decompiled_rules: List[Rule] = []
    unique_rules: Set[Rule] = set()

    for rule in list(chain.from_iterable(map(from_line_fn, rules))):
        if rule in unique_rules:
            continue

        decompiled_rules.append(rule)
        unique_rules.add(rule)

    return decompiled_rules

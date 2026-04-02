# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import List

from utils.utils import split_normalize_text


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


def split_normalize_rules_text(text: str):
    # Split into lines, remove empty lines and commented lines
    input_text_lines = split_normalize_text(text)

    # After merging all the input files, split them into top-level
    # macro definitions
    return list(split_rules(input_text_lines))

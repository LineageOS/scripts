# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import re
from functools import cache
from itertools import permutations
from typing import Dict, List, Optional, Tuple

from sepolicy.conditional_type import IConditionalType
from sepolicy.rule import rule_part

args_type = Dict[int, rule_part]
args_paths_type = Dict[int, List[List[int]]]

macro_argument_regex = re.compile(r'\$(\d+)')


@cache
def part_extract_single_match_arg_index(part: str):
    # Assuming max arg index 9

    if len(part) != 2:
        return None

    if part[0] != '$':
        return None

    if not part[1].isdigit():
        return None

    return int(part[1])


def merge_arg_values(a: Optional[args_type], b: Optional[args_type]):
    if a is None or b is None:
        return None

    if any(k in b and a[k] != b[k] for k in a):
        return None

    return a | b


@cache
def rule_part_str_regex(mrp: str):
    last_c = None
    in_arg = False
    arg_ended = False
    arg_index: Optional[int] = None
    arg_indices: List[int] = []
    arg_positions: Dict[int, Tuple[int, int]] = {}

    regex_pattern = ''
    for i, c in enumerate(mrp):
        if c == '$':
            if last_c is not None:
                assert last_c == '_'

            in_arg = True

            continue

        # Assuming max arg index 9
        if in_arg:
            assert c.isdigit(), mrp
            arg_index = int(c)

            assert arg_index not in arg_positions
            arg_positions[arg_index] = (i - 1, i + 1)
            arg_indices.append(arg_index)

            in_arg = False
            arg_ended = True
            regex_pattern += '(.+)'

            continue

        regex_pattern += c

        if arg_ended:
            assert c == '_'
            arg_ended = False

    if not arg_indices:
        return arg_indices, None, None

    regex = re.compile(regex_pattern)

    # # Find all used argument indices in this macro part
    # old_arg_indices = [int(i) for i in macro_argument_regex.findall(mrp)]
    # for arg_index in old_arg_indices:
    #     assert arg_index <= 9

    # # Escape the characters in this part of the macro rule
    # old_regex_pattern = re.escape(mrp)

    # # Replace escaped $arg with a capture group
    # old_regex_pattern = re.sub(r'\\\$(\d+)', r'(.+)', old_regex_pattern)

    # regex = re.compile(old_regex_pattern)

    # assert regex_pattern == old_regex_pattern
    # assert arg_indices == old_arg_indices

    return arg_indices, arg_positions, regex


def rule_extract_part_str(mrp: str, rp: rule_part) -> Optional[args_type]:
    # Single match args can match any type
    arg_index = part_extract_single_match_arg_index(mrp)
    if arg_index is not None:
        return {
            arg_index: rp,
        }

    if not isinstance(rp, str):
        return None

    arg_indices, _, regex = rule_part_str_regex(mrp)
    if not arg_indices:
        return {}

    assert regex is not None
    regex_match = regex.match(rp)
    if not regex_match:
        return None

    arg_values: args_type = {}
    regex_match_groups = regex_match.groups()
    for arg_group_index, arg_index in enumerate(arg_indices):
        arg_value = regex_match_groups[arg_group_index]
        arg_values[arg_index] = arg_value

    return arg_values


def rule_extract_part_set_str(mrp: List[str], rp: List[str]):
    if len(mrp) != len(rp):
        return None

    mrp_uniques = set(mrp)
    rp_uniques = set(rp)

    for mrp_part in mrp:
        # Match part to itself to see if it has any args
        arg_values = rule_extract_part_str(mrp_part, mrp_part)

        # If it has args, don't remove it
        if arg_values:
            continue

        # If it does not have args and is not present in the rule part,
        # fail extract
        if mrp_part not in rp_uniques:
            return None

        rp_uniques.remove(mrp_part)
        mrp_uniques.remove(mrp_part)

    rp_uniques_tuple = tuple(rp_uniques)

    arg_values_list: List[args_type] = []
    for permuted_mrp in permutations(mrp_uniques):
        current_arg_values = rule_extract_part_iter(
            permuted_mrp,
            rp_uniques_tuple,
        )
        if current_arg_values is None:
            continue

        arg_values_list.append(current_arg_values)

    # sets matching the same arguments in two different ways is unlikely
    # but not impossible
    num_arg_values = len(arg_values_list)
    assert num_arg_values <= 1

    if num_arg_values == 0:
        return None
    elif num_arg_values == 1:
        return arg_values_list[0]


def rule_extract_part_cond(mrp: IConditionalType, rp: rule_part):
    if not isinstance(rp, IConditionalType):
        return None

    positive_arg_values = rule_extract_part_set_str(mrp.positive, rp.positive)
    negative_arg_values = rule_extract_part_set_str(mrp.negative, rp.negative)
    return merge_arg_values(positive_arg_values, negative_arg_values)


def rule_extract_part(mrp: rule_part, rp: rule_part):
    if isinstance(mrp, str):
        return rule_extract_part_str(mrp, rp)
    else:
        assert isinstance(mrp, IConditionalType)
        return rule_extract_part_cond(mrp, rp)


def rule_extract_part_iter(
    mrp_tuple: Tuple[rule_part, ...],
    rp_tuple: Tuple[rule_part, ...],
):
    if len(mrp_tuple) != len(rp_tuple):
        return None

    arg_values: Optional[args_type] = {}
    for mrp, rp in zip(mrp_tuple, rp_tuple):
        current_arg_values = rule_extract_part(mrp, rp)

        arg_values = merge_arg_values(arg_values, current_arg_values)
        if arg_values is None:
            return None

    return arg_values

# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Iterable, List

from sepolicy.conditional_type import ConditionalType
from sepolicy.match_extract import (
    args_type,
    part_extract_single_match_arg_index,
    rule_part_str_regex,
)
from sepolicy.rule import rule_part


def rule_replace_simple_str(mrp: str, arg_values: args_type):
    arg_indices, arg_positions, _ = rule_part_str_regex(mrp)
    if not arg_indices:
        return mrp

    assert arg_positions is not None
    for arg_index, arg_position in arg_positions.items():
        if arg_index not in arg_values:
            continue

        arg_value = arg_values[arg_index]
        if not isinstance(arg_value, str):
            return None

        mrp = mrp[: arg_position[0]] + arg_value + mrp[arg_position[1] :]

    return mrp


def rule_replace_part_str(mrp: str, arg_values: args_type):
    arg_index = part_extract_single_match_arg_index(mrp)
    if arg_index is not None:
        if arg_index not in arg_values:
            return mrp

        return arg_values[arg_index]

    return rule_replace_simple_str(mrp, arg_values)


def rule_replace_part_set_str(mrp: List[str], arg_values: args_type):
    # Sets inside ConditionalType can only contain strings, and should
    # not match complex value
    new_parts: List[str] = []
    replaced = False
    for part in mrp:
        new_part = rule_replace_simple_str(part, arg_values)
        if new_part is None:
            return None

        new_parts.append(new_part)
        if part != new_part:
            replaced = True

    if not replaced:
        return mrp

    return new_parts


def rule_replace_part_cond(mrp: ConditionalType, arg_values: args_type):
    # It's impossible for conditional types to contain other conditional
    # types, match the sets like they would be simple lists of strings
    positive = rule_replace_part_set_str(mrp.positive, arg_values)
    if positive is None:
        return None

    negative = rule_replace_part_set_str(mrp.negative, arg_values)
    if negative is None:
        return None

    return ConditionalType(positive, negative, mrp.is_all)


def rule_replace_part(mrp: rule_part, arg_values: args_type):
    if isinstance(mrp, str):
        return rule_replace_part_str(mrp, arg_values)
    else:
        assert isinstance(mrp, ConditionalType)
        return rule_replace_part_cond(mrp, arg_values)


def rule_replace_part_iter(
    mrp_tuple: Iterable[rule_part],
    arg_values: args_type,
):
    filled_parts: List[rule_part] = []
    for mrp in mrp_tuple:
        filled_mrp = rule_replace_part(mrp, arg_values)
        if filled_mrp is None:
            return None

        filled_parts.append(filled_mrp)

    return filled_parts

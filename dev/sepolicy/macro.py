# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import re
from typing import (
    Dict,
    FrozenSet,
    List,
    Set,
    Tuple,
)

from sepolicy.classmap import Classmap
from sepolicy.rule import Rule, flatten_parts, unpack_line
from sepolicy.rules import split_normalize_rules_text
from sepolicy.source_rule import (
    SourceRuleParser,
    trim_ioctl_str,
    unpack_ioctls,
)
from sepolicy.varargs import Ioctls
from utils.utils import Color, color_print

MACRO_DEFINITION_START = 'define(`'


def _macro_name_body(macro: str):
    if not macro.startswith(MACRO_DEFINITION_START):
        return None, macro

    assert macro.endswith(')'), macro
    macro = macro[len(MACRO_DEFINITION_START) : -1]
    name, body = macro.split("'", 1)

    assert body[0] == ',', body
    body = body[1:]
    body = body.strip()

    # Not all macros have a quoted body
    assert (body[0] == '`') == (body[-1] == "'")
    if body[0] == '`' and body[-1] == "'":
        body = body[1:-1]

    body = body.strip()

    return name, body


def macro_name(macro: str):
    return _macro_name_body(macro)[0]


def macro_name_body(macro: str):
    name, body = _macro_name_body(macro)
    if name is None:
        # color_print(f'Rule {macro} present among macros', color=Color.YELLOW)
        return None

    return name, body


def rule_body(text: str):
    name, body = _macro_name_body(text)
    if name is not None:
        color_print(f'Macro {name} present among rules', color=Color.YELLOW)
        return None

    return body


macro_arity_pattern = re.compile(r'\$([1-9][0-9]*)')


def macro_arity(body: str):
    found_args = macro_arity_pattern.finditer(body)
    used_args = set(int(m.group(1)) for m in found_args)
    return max(used_args) if used_args else 0


def categorize_macros(expanded_macros: List[Tuple[str, str]]):
    macros: List[Tuple[str, str]] = []
    class_sets: List[Tuple[str, str]] = []
    perms: List[Tuple[str, str]] = []

    empty_macros: Set[str] = set()
    for name, body in expanded_macros:
        if not body:
            if name in empty_macros:
                continue

            color_print(f'Empty macro {name}', color=Color.YELLOW)
            empty_macros.add(name)
            continue

        # Handled in format_ioctl_defines()
        assert not body.startswith('0x'), f'{name}:\n{body}'

        macro_tuple = (name, body)

        if '_class_set' in name:
            class_sets.append(macro_tuple)
        elif '_perms' in name:
            perms.append(macro_tuple)
        else:
            macros.append(macro_tuple)

    return macros, class_sets, perms


def parse_macros(
    classmap: Classmap,
    expanded_macros: List[Tuple[str, str]],
):
    expanded_macro_rules: List[Tuple[str, List[Rule]]] = []
    unqiue_macro_name_rules: Set[Tuple[str, FrozenSet[Rule]]] = set()
    unique_macro_rules: Dict[FrozenSet[Rule], str] = {}
    invalid_macro_names: Set[str] = set()
    macro_names: Set[str] = set()

    for name, body in expanded_macros:
        rules: List[Rule] = []

        parser = SourceRuleParser(
            rules.append,
            classmap,
        )

        try:
            for rule_text in split_normalize_rules_text(body):
                parser.parse_line(rule_text)
        except (ValueError, AssertionError) as e:
            if name not in invalid_macro_names:
                color_print(f'Invalid macro {name}: {e}', color=Color.YELLOW)
                invalid_macro_names.add(name)
            continue

        hashable_rules = frozenset(rules)
        hashable_macro_name_rules = (name, hashable_rules)

        if hashable_macro_name_rules in unqiue_macro_name_rules:
            continue

        # This is done to avoid the macros from being discard in favor of the
        # other macro with the same name
        # TODO: find better solution, although it's not really possible to
        # distinguish between the two
        if hashable_rules in unique_macro_rules:
            duplicate_macro_name = unique_macro_rules[hashable_rules]
            color_print(
                f'Macro {name} has same rules as {duplicate_macro_name}',
                color=Color.YELLOW,
            )
            continue

        if name in macro_names:
            print(f'Macro {name} has multiple variants')

        expanded_macro_rules.append((name, rules))
        unique_macro_rules[hashable_rules] = name
        unqiue_macro_name_rules.add(hashable_macro_name_rules)
        macro_names.add(name)

    return expanded_macro_rules


def parse_perms(perms: List[Tuple[str, str]]):
    decompiled_perms: List[Tuple[str, Set[str]]] = []

    for name, text in perms:
        parts = unpack_line(
            text,
            '{',
            '}',
            ' ',
            open_by_default=True,
            ignored_chars=';',
        )
        parts_set = set(flatten_parts(parts))
        decompiled_perms.append((name, parts_set))

    # Prioritize replacement of largest perm macros
    decompiled_perms.sort(key=lambda np: len(np[1]), reverse=True)

    return decompiled_perms


def ioctl_type_name(is_nlmsg: bool):
    return 'nlmsg' if is_nlmsg else 'ioctl'


def parse_ioctls(
    ioctls: List[Tuple[str, str]],
    is_nlmsg: bool,
):
    ioctl_type_name_cap = ioctl_type_name(is_nlmsg).capitalize()
    decompiled_ioctls: List[Tuple[str, Ioctls]] = []

    for name, text in ioctls:
        parts = unpack_line(
            text,
            '{',
            '}',
            ' \n',
            open_by_default=True,
            ignored_chars=';',
        )
        flattened_parts = list(flatten_parts(parts))
        try:
            unpacked_ioctls = unpack_ioctls(flattened_parts)
        except ValueError:
            color_print(
                f'{ioctl_type_name_cap} macro {name} contains invalid ioctls: {text}',
                color=Color.RED,
            )
            continue

        decompiled_ioctls.append((name, unpacked_ioctls))

    return decompiled_ioctls


def parse_ioctl_defines(
    ioctl_defines: List[Tuple[str, str]],
    verbose: bool,
    is_nlmsg: bool,
):
    ioctl_type_name_cap = ioctl_type_name(is_nlmsg).capitalize()
    decompiled_ioctl_defines: Dict[int, str] = {}

    duplicate_ioctls: Set[int] = set()
    for name, text in ioctl_defines:
        value = trim_ioctl_str(text)

        if value not in decompiled_ioctl_defines:
            decompiled_ioctl_defines[value] = name
            continue

        if name == decompiled_ioctl_defines[value]:
            continue

        if value in duplicate_ioctls:
            continue

        existing_name = decompiled_ioctl_defines[value]
        # This happens very often, but it's not exactly good
        if verbose:
            color_print(
                f'{ioctl_type_name_cap} {name}={value} already defined as {existing_name}',
                color=Color.YELLOW,
            )
        duplicate_ioctls.add(value)

    return decompiled_ioctl_defines

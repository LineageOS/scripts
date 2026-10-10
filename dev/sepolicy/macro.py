# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import re
from itertools import product
from typing import (
    Dict,
    FrozenSet,
    List,
    NamedTuple,
    Optional,
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

ARG_IFELSE_MARKER = 'ARG_IFELSE'
ARG_ELSE_MARKER = 'ARG_ELSE'
ARG_END_MARKER = 'ARG_END'

arg_pattern = re.compile(r'\$([1-9][0-9]*)')


class ArgCondition(NamedTuple):
    arg_index: int
    value: str
    equal: bool


class MacroVariant(NamedTuple):
    name: str
    rules: List[Rule]
    conditions: Tuple[ArgCondition, ...] = ()


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


def _conditions_consistent(conditions: Tuple[ArgCondition, ...]):
    equal_values = {(c.arg_index, c.value) for c in conditions if c.equal}
    equal = dict(equal_values)
    if len(equal) != len(equal_values):
        return False

    return all(c.equal or equal.get(c.arg_index) != c.value for c in conditions)


def macro_body_variants(body: str):
    segments: List[List[Tuple[str, Tuple[ArgCondition, ...]]]] = []
    lines: List[str] = []
    condition: Optional[ArgCondition] = None
    then_text: Optional[str] = None
    in_branch = False

    for line in body.splitlines():
        words = line.split(maxsplit=2)
        if words[:1] == [ARG_IFELSE_MARKER]:
            assert not in_branch, body
            segments.append([('\n'.join(lines), ())])
            arg_match = arg_pattern.fullmatch(words[1])
            value = words[2] if len(words) > 2 else ''
            condition = None
            if arg_match is not None:
                condition = ArgCondition(int(arg_match.group(1)), value, True)
            then_text = None
            in_branch = True
        elif words == [ARG_ELSE_MARKER]:
            assert in_branch, body
            then_text = '\n'.join(lines)
        elif words == [ARG_END_MARKER]:
            assert in_branch and then_text is not None, body
            else_text = '\n'.join(lines)
            if condition is None:
                segments.append([(else_text, ())])
            else:
                segments.append(
                    [
                        (then_text, (condition,)),
                        (else_text, (condition._replace(equal=False),)),
                    ]
                )
            in_branch = False
        else:
            lines.append(line)
            continue

        lines = []

    assert not in_branch, body
    segments.append([('\n'.join(lines), ())])

    variants: List[Tuple[str, Tuple[ArgCondition, ...]]] = []
    for choice in product(*segments):
        conditions = tuple(c for _, cs in choice for c in cs)
        if not _conditions_consistent(conditions):
            continue

        text = '\n'.join(t for t, _ in choice if t)
        variants.append((text, conditions))

    return variants


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
    expanded_macro_rules: List[MacroVariant] = []
    unqiue_macro_name_rules: Set[
        Tuple[str, FrozenSet[Rule], Tuple[ArgCondition, ...]]
    ] = set()
    unique_macro_rules: Dict[FrozenSet[Rule], str] = {}
    invalid_macro_names: Set[str] = set()
    macro_names: Set[str] = set()

    for name, body in expanded_macros:
        for variant_body, conditions in macro_body_variants(body):
            rules: List[Rule] = []

            parser = SourceRuleParser(
                rules.append,
                classmap,
            )

            try:
                for rule_text in split_normalize_rules_text(variant_body):
                    parser.parse_line(rule_text)
            except (ValueError, AssertionError) as e:
                if name not in invalid_macro_names:
                    color_print(
                        f'Invalid macro {name}: {e}',
                        color=Color.YELLOW,
                    )
                    invalid_macro_names.add(name)
                continue

            hashable_rules = frozenset(rules)
            hashable_macro_name_rules = (name, hashable_rules, conditions)

            if hashable_macro_name_rules in unqiue_macro_name_rules:
                continue

            # This is done to avoid the macros from being discard in favor of
            # the other macro with the same name
            # TODO: find better solution, although it's not really possible to
            # distinguish between the two
            if hashable_rules in unique_macro_rules:
                duplicate_macro_name = unique_macro_rules[hashable_rules]
                color_print(
                    f'Macro {name} has same rules as {duplicate_macro_name}',
                    color=Color.YELLOW,
                )
                continue

            if name in macro_names and not conditions:
                print(f'Macro {name} has multiple variants')

            expanded_macro_rules.append(MacroVariant(name, rules, conditions))
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

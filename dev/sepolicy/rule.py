# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import re
from enum import StrEnum
from typing import FrozenSet, Generator, List, Optional, Tuple, Union

from sepolicy.class_set import ClassSet
from sepolicy.conditional_type import IConditionalType

macro_argument_regex = re.compile(r'\$(\d+)')

raw_part = Union[str, List['raw_part']]
raw_parts_list = List[raw_part]
rule_part = Union[str, IConditionalType, ClassSet]
rule_hash_value = Union[rule_part, FrozenSet[str]]


RULE_DYNAMIC_PARTS_INDEX = 1


def is_type_generated(part: rule_part):
    if not isinstance(part, str):
        return False

    return part.startswith('base_typeattr_')


def unpack_line(
    rule: str,
    open_char: str,
    close_char: str,
    separators: str,
    open_by_default: bool = False,
    ignored_chars: str = '',
) -> raw_parts_list:
    stack: List[raw_parts_list] = []
    current: raw_parts_list = []
    token = ''

    def add_token():
        nonlocal token

        if token:
            current.append(token)
            token = ''

    if open_by_default:
        rule = f'{open_char}{rule}{close_char}'

    for c in rule:
        if c in ignored_chars:
            continue

        if c == open_char:
            add_token()
            stack.append(current)
            current = []
        elif c == close_char:
            add_token()
            last = stack.pop()
            last.append(current)
            current = last
        elif c in separators:
            add_token()
        else:
            token += c

    assert isinstance(current[0], list)

    return current[0] if current else []


def flatten_parts(parts: raw_part) -> Generator[str, None, None]:
    if isinstance(parts, str):
        yield parts
        return

    assert isinstance(parts, list)

    for part in parts:
        if isinstance(part, list):
            yield from flatten_parts(part)
        else:
            yield part


class RuleType(StrEnum):
    ALLOW = 'allow'
    ALLOWXPERM = 'allowxperm'
    ATTRIBUTE = 'attribute'
    AUDITALLOW = 'auditallow'
    AUDITALLOWXPERM = 'auditallowxperm'
    DONTAUDIT = 'dontaudit'
    DONTAUDITXPERM = 'dontauditxperm'
    EXPANDATTRIBUTE = 'expandattribute'
    GENFSCON = 'genfscon'
    NEVERALLOW = 'neverallow'
    NEVERALLOWXPERM = 'neverallowxperm'
    TYPE = 'type'
    TYPE_TRANSITION = 'type_transition'
    TYPEATTRIBUTE = 'typeattribute'


ALLOW_RULE_TYPES = [
    RuleType.ALLOW,
    RuleType.NEVERALLOW,
    RuleType.AUDITALLOW,
    RuleType.DONTAUDIT,
]


IOCTL_RULE_TYPES = [
    RuleType.ALLOWXPERM,
    RuleType.AUDITALLOWXPERM,
    RuleType.NEVERALLOWXPERM,
    RuleType.DONTAUDITXPERM,
]

CLASS_SETS_RULE_TYPES = ALLOW_RULE_TYPES + IOCTL_RULE_TYPES
CONTEXTS_LABEL_START = 'u:object_r:'
CONTEXTS_LABEL_END = ':s0'


def trim_contexts_label(t: str):
    assert t.startswith(CONTEXTS_LABEL_START)
    assert t.endswith(CONTEXTS_LABEL_END)
    return t[len(CONTEXTS_LABEL_START) : -len(CONTEXTS_LABEL_END)]


def join_varargs(varargs: Tuple[str, ...]):
    s = ' '.join(varargs)

    if len(varargs) > 1:
        s = '{ ' + s + ' }'

    return s


def format_rule(rule: Rule):
    match rule.rule_type:
        case (
            RuleType.ALLOW
            | RuleType.NEVERALLOW
            | RuleType.AUDITALLOW
            | RuleType.DONTAUDIT
        ):
            return '{} {} {}:{} {};'.format(
                rule.rule_type,
                rule.parts[0],
                rule.parts[1],
                rule.parts[2],
                join_varargs(rule.varargs),
            )
        case (
            RuleType.ALLOWXPERM
            | RuleType.AUDITALLOWXPERM
            | RuleType.NEVERALLOWXPERM
            | RuleType.DONTAUDITXPERM
        ):
            return '{} {} {}:{} {} {};'.format(
                rule.rule_type,
                rule.parts[0],
                rule.parts[1],
                rule.parts[2],
                rule.parts[3],
                join_varargs(rule.varargs),
            )
        case RuleType.TYPE:
            varargs = sorted(rule.varargs)
            assert isinstance(rule.parts[0], str)
            parts = (rule.parts[0], *varargs)
            parts_str = ', '.join(parts)
            return '{} {};'.format(rule.rule_type, parts_str)
        case RuleType.TYPE_TRANSITION:
            assert len(rule.varargs) in [0, 1]

            if len(rule.varargs) == 1:
                name = f'{list(rule.varargs)[0]} '
            else:
                name = ''

            return '{} {} {}:{} {}{};'.format(
                rule.rule_type,
                rule.parts[0],
                rule.parts[1],
                rule.parts[2],
                name,
                rule.parts[-1],
            )
        case RuleType.GENFSCON:
            return '{} {} {} {}{}{}'.format(
                rule.rule_type,
                rule.parts[0],
                rule.parts[1],
                CONTEXTS_LABEL_START,
                rule.parts[2],
                CONTEXTS_LABEL_END,
            )
        case (
            RuleType.ATTRIBUTE
            | RuleType.TYPEATTRIBUTE
            | RuleType.EXPANDATTRIBUTE
        ):
            parts_str = ' '.join(map(str, rule.parts))
            return f'{rule.rule_type} {parts_str};'
        case _:
            assert rule.is_macro
            parts_str = ', '.join(map(str, rule.parts))
            return f'{rule.rule_type}({parts_str})'


class Rule:
    def __init__(
        self,
        rule_type: str,
        parts: Tuple[rule_part, ...],
        varargs: Tuple[str, ...],
        is_macro: bool = False,
    ):
        self.rule_type = rule_type
        self.parts = parts
        self.varargs = tuple(sorted(varargs))
        self.is_macro = is_macro
        self.varargs_hash_value = frozenset(varargs)
        self.hash_values: Tuple[rule_hash_value, ...] = (
            self.rule_type,
            *self.parts,
            frozenset(varargs),
        )

        # Postpone hash calculation so that ConditionalTypes are fully
        # gathered and ConditionalTypeRedirect can find them
        self.__hash: Optional[int] = None

    def __str__(self):
        return format_rule(self)

    def __eq__(self, other: object):
        assert isinstance(other, Rule)

        return self.hash_values == other.hash_values

    def __hash__(self):
        if self.__hash is None:
            self.__hash = hash(self.hash_values)

        return self.__hash


def rule_sort_key(rule: Rule):
    compare_values: List[Union[rule_part, Tuple[str, ...]]] = [
        rule.rule_type,
        *rule.parts,
        rule.varargs,
    ]

    if rule.rule_type == RuleType.TYPE:
        order = -2
    elif rule.rule_type == RuleType.TYPEATTRIBUTE:
        order = -1
    elif rule.is_macro:
        order = 0
    else:
        order = 1

    return (order, *(str(h) for h in compare_values))

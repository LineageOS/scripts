# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import re
from enum import StrEnum
from typing import (
    Dict,
    FrozenSet,
    Generator,
    List,
    Optional,
    Set,
    Tuple,
    Union,
)

from sepolicy.class_set import ClassSet
from sepolicy.conditional_type import ConditionalType
from sepolicy.varargs import Ioctls, Perms, Types, TypeTransitionTag

macro_argument_regex = re.compile(r'\$(\d+)')

raw_part = Union[str, List['raw_part']]
raw_parts_list = List[raw_part]
rule_part = Union[str, ConditionalType, ClassSet]
rule_hash_value = Union[rule_part, Perms, Ioctls, TypeTransitionTag, Types]


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

    if open_by_default:
        rule = f'{open_char}{rule}{close_char}'

    stack_append = stack.append
    stack_pop = stack.pop

    i = 0
    n = len(rule)
    while i < n:
        c = rule[i]

        if c in ignored_chars:
            i += 1
            continue

        if c == open_char:
            stack_append(current)
            current = []
            i += 1
            continue

        if c == close_char:
            last = stack_pop()
            last.append(current)
            current = last
            i += 1
            continue

        if c in separators:
            i += 1
            continue

        start = i
        i += 1
        while i < n:
            c = rule[i]
            if (
                c == open_char
                or c == close_char
                or c in separators
                or c in ignored_chars
            ):
                break
            i += 1

        current.append(rule[start:i])

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


def get_class_name_perms(
    class_name: Union[str, ClassSet],
    class_perms: Optional[Dict[str, List[Tuple[str, Set[str]]]]] = None,
):
    if class_perms is None:
        return None

    if isinstance(class_name, str):
        return class_perms.get(class_name, None)

    class_name_perms = None
    for cn in class_name:
        cnp = class_perms.get(cn, None)
        if class_name_perms is None:
            class_name_perms = cnp
        else:
            if cnp != class_name_perms:
                return None

    return class_name_perms


def format_rule(
    rule: Rule,
    class_perms: Optional[Dict[str, List[Tuple[str, Set[str]]]]] = None,
    ioctls: Optional[List[Tuple[str, Ioctls]]] = None,
    ioctl_defines: Optional[Dict[int, str]] = None,
    nlmsgs: Optional[List[Tuple[str, Ioctls]]] = None,
    nlmsg_defines: Optional[Dict[int, str]] = None,
):
    match rule.rule_type:
        case (
            RuleType.ALLOW
            | RuleType.NEVERALLOW
            | RuleType.AUDITALLOW
            | RuleType.DONTAUDIT
        ):
            assert isinstance(rule.varargs, Perms)
            assert isinstance(rule.parts[2], (str, ClassSet))

            class_name = rule.parts[2]
            class_name_perms = get_class_name_perms(
                class_name,
                class_perms,
            )
            perms_str = rule.varargs.format(
                class_perms=class_name_perms,
            )

            return '{} {} {}:{} {};'.format(
                rule.rule_type,
                rule.parts[0],
                rule.parts[1],
                rule.parts[2],
                perms_str,
            )
        case (
            RuleType.ALLOWXPERM
            | RuleType.AUDITALLOWXPERM
            | RuleType.NEVERALLOWXPERM
            | RuleType.DONTAUDITXPERM
        ):
            assert isinstance(rule.varargs, Ioctls)

            if rule.parts[3] == 'ioctl':
                varargs_str = rule.varargs.format(
                    ioctls=ioctls,
                    ioctl_defines=ioctl_defines,
                )
            elif rule.parts[3] == 'nlmsg':
                varargs_str = rule.varargs.format(
                    ioctls=nlmsgs,
                    ioctl_defines=nlmsg_defines,
                )
            else:
                assert False, rule

            return '{} {} {}:{} {} {};'.format(
                rule.rule_type,
                rule.parts[0],
                rule.parts[1],
                rule.parts[2],
                rule.parts[3],
                varargs_str,
            )
        case RuleType.TYPE:
            if isinstance(rule.varargs, Types):
                types_str = str(rule.varargs)
            else:
                types_str = ''

            return '{} {}{};'.format(
                rule.rule_type,
                rule.parts[0],
                types_str,
            )
        case RuleType.TYPE_TRANSITION:
            if isinstance(rule.varargs, TypeTransitionTag):
                name = f'{rule.varargs} '
            elif rule.varargs is None:
                name = ''
            else:
                assert False

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
        varargs: Optional[
            Union[
                Perms,
                Ioctls,
                TypeTransitionTag,
                Types,
            ]
        ] = None,
        is_macro: bool = False,
        expanded_rules: Optional[FrozenSet[Rule]] = None,
    ):
        self.rule_type = rule_type
        self.parts = parts
        self.varargs = varargs
        self.is_macro = is_macro
        self.expanded_rules = expanded_rules
        self.hash_values: Tuple[Optional[rule_hash_value], ...] = (
            self.rule_type,
            *self.parts,
            varargs,
        )
        self.__hash = hash(self.hash_values)

    def __str__(self):
        return format_rule(self)

    def format(
        self,
        class_perms: Dict[str, List[Tuple[str, Set[str]]]],
        ioctls: List[Tuple[str, Ioctls]],
        ioctl_defines: Dict[int, str],
        nlmsgs: List[Tuple[str, Ioctls]],
        nlmsg_defines: Dict[int, str],
    ):
        return format_rule(
            self,
            class_perms=class_perms,
            ioctls=ioctls,
            ioctl_defines=ioctl_defines,
            nlmsgs=nlmsgs,
            nlmsg_defines=nlmsg_defines,
        )

    def __eq__(self, other: object):
        assert isinstance(other, Rule)

        return self.hash_values == other.hash_values

    def __hash__(self):
        return self.__hash


def rule_type_order(rule: Rule):
    if rule.rule_type == RuleType.TYPE:
        return -3
    elif rule.rule_type == RuleType.ATTRIBUTE:
        return -2
    elif rule.rule_type == RuleType.TYPEATTRIBUTE:
        return -1
    else:
        return 1


def rule_sort_key(rule: Rule):
    compare_values: List[
        Union[
            rule_part,
            Tuple[str, ...],
            Optional[
                Union[
                    Perms,
                    Ioctls,
                    TypeTransitionTag,
                    Types,
                ]
            ],
        ]
    ] = [
        rule.rule_type,
        *rule.parts,
        rule.varargs,
    ]

    return tuple(str(h) for h in compare_values)

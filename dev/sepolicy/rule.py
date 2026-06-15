# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import re
from functools import cache
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
from sepolicy.varargs import (
    Ioctls,
    OrderedPerms,
    Perms,
    Types,
    TypeTransitionTag,
)

macro_argument_regex = re.compile(r'\$(\d+)')


@cache
def _get_tokenizer(
    open_char: str,
    close_char: str,
    separators: str,
    ignored_chars: str,
) -> re.Pattern[str]:
    delimiters = open_char + close_char + separators + ignored_chars
    pattern = (
        f'[{re.escape(open_char + close_char)}]|[^{re.escape(delimiters)}]+'
    )
    return re.compile(pattern)


raw_part = Union[str, List['raw_part']]
raw_parts_list = List[raw_part]
rule_part = Union[str, ConditionalType, ClassSet]
rule_hash_value = Union[
    rule_part,
    OrderedPerms,
    Perms,
    Ioctls,
    TypeTransitionTag,
    Types,
]


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

    tokenizer = _get_tokenizer(
        open_char,
        close_char,
        separators,
        ignored_chars,
    )

    for token in tokenizer.findall(rule):
        if token == open_char:
            stack_append(current)
            current = []
        elif token == close_char:
            last = stack_pop()
            last.append(current)
            current = last
        else:
            current.append(token)

    if not current:
        return []

    assert isinstance(current[0], list)

    return current[0]


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


class RuleType:
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
                OrderedPerms,
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
        class_perms: Optional[Dict[str, List[Tuple[str, Set[str]]]]],
        ioctls: Optional[List[Tuple[str, Ioctls]]],
        ioctl_defines: Optional[Dict[int, str]],
        nlmsgs: Optional[List[Tuple[str, Ioctls]]],
        nlmsg_defines: Optional[Dict[int, str]],
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


def _rule_used_types(rule: Rule, used_types: Set[str]):
    def handle_type(t: rule_part):
        if isinstance(t, str):
            used_types.add(t)
        elif isinstance(t, ConditionalType):
            for p in t.positive:
                used_types.add(p)
            for n in t.negative:
                used_types.add(n)

    match rule.rule_type:
        case (
            RuleType.ALLOW
            | RuleType.NEVERALLOW
            | RuleType.AUDITALLOW
            | RuleType.DONTAUDIT
            | RuleType.ALLOWXPERM
            | RuleType.NEVERALLOWXPERM
            | RuleType.AUDITALLOWXPERM
            | RuleType.DONTAUDITXPERM
            | RuleType.TYPE_TRANSITION
        ):
            handle_type(rule.parts[0])
            handle_type(rule.parts[1])
        case RuleType.GENFSCON:
            handle_type(rule.parts[2])
        case RuleType.TYPE | RuleType.TYPEATTRIBUTE:
            pass
        case RuleType.ATTRIBUTE | RuleType.EXPANDATTRIBUTE:
            # TODO: figure out if these should be taken into account
            pass
        case _:
            assert False, rule


def rule_used_types(rule: Rule):
    used_types: Set[str] = set()

    if rule.is_macro:
        assert rule.expanded_rules is not None
        for r in rule.expanded_rules:
            _rule_used_types(r, used_types)
    else:
        _rule_used_types(rule, used_types)

    return used_types


def _rule_defined_types(
    rule: Rule,
    defined_types: Set[str],
):
    if rule.rule_type != RuleType.TYPE:
        return None

    assert isinstance(rule.parts[0], str)
    defined_types.add(rule.parts[0])


def rule_defined_types(rule: Rule):
    defined_types: Set[str] = set()

    if rule.is_macro:
        assert rule.expanded_rules is not None
        for r in rule.expanded_rules:
            _rule_defined_types(r, defined_types)
    else:
        _rule_defined_types(rule, defined_types)

    return defined_types

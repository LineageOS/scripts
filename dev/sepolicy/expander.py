# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from collections import defaultdict
from typing import (
    Dict,
    FrozenSet,
    Iterator,
    Set,
    Tuple,
    Union,
)

from sepolicy.conditional_type import ConditionalType
from sepolicy.rule import Rule, RuleType, rule_part
from sepolicy.rule_container import RuleContainer
from sepolicy.varargs import Ioctls, Perms

EXPAND_TYPES = frozenset(
    {
        RuleType.ALLOW,
        RuleType.AUDITALLOW,
        RuleType.DONTAUDIT,
        RuleType.ALLOWXPERM,
        RuleType.AUDITALLOWXPERM,
        RuleType.DONTAUDITXPERM,
    }
)


def str_part(rule: Rule, index: int) -> str:
    part = rule.parts[index]
    assert isinstance(part, str)
    return part


def varargs_subset(a: Union[Perms, Ioctls], b: Union[Perms, Ioctls]) -> bool:
    if isinstance(a, Perms) and isinstance(b, Perms):
        return a <= b
    elif isinstance(a, Ioctls) and isinstance(b, Ioctls):
        return a <= b

    assert False


class Resolver:
    def __init__(self, rules: RuleContainer):
        self.__members: Dict[str, Set[str]] = defaultdict(set)
        self.__types: Set[str] = set()
        self.__attributes: Set[str] = set()
        self.__expanded: Set[str] = set()
        self.__excluded: Dict[str, Set[str]] = defaultdict(set)
        self.__cache: Dict[Tuple[str, bool], FrozenSet[str]] = {}

        for rule in rules:
            self.__add_rule(rule)

    def __add_rule(self, rule: Rule) -> None:
        match rule.rule_type:
            case RuleType.TYPE:
                src = str_part(rule, 0)
                self.__types.add(src)
            case RuleType.ATTRIBUTE:
                src = str_part(rule, 0)
                self.__attributes.add(src)
            case RuleType.TYPEATTRIBUTE:
                src = str_part(rule, 0)
                dst = str_part(rule, 1)
                self.__members[dst].add(src)
            case RuleType.EXPANDATTRIBUTE if rule.parts[1] == 'true':
                src = str_part(rule, 0)
                self.__expanded.add(src)
            case _:
                pass

    def is_attribute(self, name: str) -> bool:
        return name in self.__attributes

    def exclude_member(self, attribute: str, member: str) -> bool:
        # Drop a single member from an attribute's effective expansion,
        # mirroring how a recovery build (with the not_recovery()-guarded
        # membership removed) would expand it. Returns True if newly excluded.
        excluded = self.__excluded[attribute]
        if member in excluded:
            return False
        excluded.add(member)
        self.__cache.clear()
        return True

    def resolve(
        self,
        name: str,
        expand_all_attrs: bool,
    ) -> FrozenSet[str]:
        key = (name, expand_all_attrs)
        cached = self.__cache.get(key)
        if cached is not None:
            return cached

        members = self.__members.get(name)
        if members is None:
            result = (
                frozenset[str]()
                if name in self.__attributes
                else frozenset((name,))
            )
        elif expand_all_attrs or name in self.__expanded:
            result = frozenset(
                t
                for member in members
                for t in self.resolve(member, expand_all_attrs)
            )
        else:
            result = frozenset((name,))

        excluded = self.__excluded.get(name)
        if excluded:
            result = result - excluded

        self.__cache[key] = result
        return result

    def resolve_part(
        self,
        part: rule_part,
        expand_all_attrs: bool = False,
    ) -> FrozenSet[str]:
        if isinstance(part, str):
            return self.resolve(part, expand_all_attrs)

        assert isinstance(part, ConditionalType)
        return self.resolve_conditional(part)

    def resolve_conditional(self, part: ConditionalType) -> FrozenSet[str]:
        if part.is_all:
            return frozenset(self.__types)

        result: Set[str] = set() if part.positive else set(self.__types)
        for name in part.positive:
            result |= self.resolve(name, True)
        for name in part.negative:
            result -= self.resolve(name, True)
        return frozenset(result)

    def __normalize_target(self, src: str, dst: str) -> str:
        if src == dst and src not in self.__attributes:
            return 'self'

        return dst

    def expanded_pairs(self, rule: Rule) -> Iterator[Tuple[str, str]]:
        src, dst = rule.parts[0], rule.parts[1]

        # self expands src per-member, keeping the literal 'self'.
        srcs = self.resolve_part(src, expand_all_attrs=dst == 'self')
        if dst == 'self':
            yield from ((s, 'self') for s in srcs)
            return

        tgts = self.resolve_part(dst)
        for s in srcs:
            for t in tgts:
                yield s, self.__normalize_target(s, t)

    def expand_rule(self, rule: Rule) -> Iterator[Rule]:
        rest = rule.parts[2:]
        for s, t in self.expanded_pairs(rule):
            yield Rule(rule.rule_type, (s, t, *rest), rule.varargs)

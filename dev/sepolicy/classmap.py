# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from sepolicy.rule_container import RuleContainer
from sepolicy.varargs import OrderedPerms
from utils.utils import split_normalize_text


def extract_classmap(text: str) -> Dict[str, List[str]]:
    lines = split_normalize_text(text)
    text = ''.join(lines)
    tokens = text.split()

    classes_map: Dict[str, List[str]] = {}
    commons_map: Dict[str, List[str]] = {}

    i = 0
    while i < len(tokens):
        if tokens[i] == 'common':
            i += 1
            is_common = True
        elif tokens[i] == 'class':
            i += 1
            is_common = False
        else:
            assert False

        name = tokens[i]
        i += 1

        perms: List[str] = []

        if tokens[i] == 'inherits':
            i += 1

            assert not is_common

            inherit_name = tokens[i]
            i += 1

            inherited_perms = commons_map[inherit_name]
            perms.extend(inherited_perms)

        if tokens[i] == '{':
            i += 1
            while tokens[i] != '}':
                perms.append(tokens[i])
                i += 1
            i += 1

        if is_common:
            assert name not in commons_map
            commons_map[name] = perms
        else:
            assert name not in classes_map
            classes_map[name] = perms

    return classes_map


def extract_classmap_from_rules(rules: RuleContainer):
    class_name_common_map: Dict[str, List[str]] = defaultdict(list)
    classes_map: Dict[str, List[str]] = {}
    commons_map: Dict[str, List[str]] = {}

    for rule in rules:
        if rule.rule_type == 'common':
            assert isinstance(rule.varargs, OrderedPerms)
            assert len(rule.parts) == 1

            name = rule.parts[0]
            assert isinstance(name, str)
            assert name not in commons_map

            commons_map[name] = list(rule.varargs)

        elif rule.rule_type == 'class':
            assert isinstance(rule.varargs, OrderedPerms)
            assert len(rule.parts) == 1

            name = rule.parts[0]
            assert isinstance(name, str)
            assert name not in classes_map

            classes_map[name] = list(rule.varargs)

        elif rule.rule_type == 'classcommon':
            assert len(rule.parts) == 2

            class_name = rule.parts[0]
            common_name = rule.parts[1]

            assert isinstance(class_name, str)
            assert isinstance(common_name, str)

            class_name_common_map[class_name].append(common_name)

        elif rule.rule_type == 'classorder':
            continue

        else:
            continue

    for class_name, common_names in class_name_common_map.items():
        assert class_name in classes_map

        inherited_perms: List[str] = []
        for common_name in common_names:
            inherited_perms.extend(commons_map[common_name])

        classes_map[class_name] = inherited_perms + classes_map[class_name]

    return classes_map


class Classmap:
    def __init__(self, class_perms_map: Dict[str, List[str]]):
        self.__class_perms_map = class_perms_map

    @classmethod
    def from_text(cls, text: str):
        return cls(extract_classmap(text))

    @classmethod
    def from_rules(cls, rules: RuleContainer):
        return cls(extract_classmap_from_rules(rules))

    def class_types(self, t: str):
        for key in self.__class_perms_map:
            if key.endswith(t):
                yield key

    def class_perms(self, class_name: str):
        return self.__class_perms_map[class_name][:]

    def class_perms_set(self, class_name: str):
        return set(self.__class_perms_map[class_name])

# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import re
from functools import cache
from pathlib import Path
from typing import Dict, List, Optional, Set

from sepolicy.conditional_type import ConditionalType
from sepolicy.rule import (
    Rule,
    RuleType,
    rule_part,
    rule_sort_key,
    rule_type_order,
)
from sepolicy.rule_container import RuleContainer
from sepolicy.source_policy import Source
from sepolicy.varargs import Types


@cache
def extract_domain_type(domain: str):
    domain = re.sub(r'^vendor_', '', domain)
    domain = re.sub(r'_exec$', '', domain)
    domain = re.sub(r'_client$', '', domain)
    domain = re.sub(r'_server$', '', domain)
    domain = re.sub(r'_default$', '', domain)
    domain = re.sub(r'_hwservice$', '', domain)
    domain = re.sub(r'_service$', '', domain)
    domain = re.sub(r'_qti$', '', domain)
    return domain


DEVICE_TYPE_RULES_NAME = 'device.te'
SERVICE_TYPE_RULES_NAME = 'service.te'
HWSERVICE_TYPE_RULES_NAME = 'hwservice.te'
FILE_TYPE_RULES_NAME = 'file.te'
PROPERTY_RULES_NAME = 'property.te'
LEFTOVER_RULES_NAME = 'leftover.te'
ATTRIBUTE_RULES_NAME = 'attributes'


def domain_type(rule: Rule):
    domain = rule.parts[0]
    if not isinstance(domain, str) and len(rule.parts) >= 2:
        domain = rule.parts[1]

    if not isinstance(domain, str):
        return LEFTOVER_RULES_NAME

    t = extract_domain_type(domain)
    return f'{t}.te'


def rule_simple_type_name(rule: Rule):
    if rule.rule_type == RuleType.TYPE.value:
        assert isinstance(rule.varargs, Types)

        if 'dev_type' in rule.varargs:
            return DEVICE_TYPE_RULES_NAME, False
        elif 'file_type' in rule.varargs or 'fs_type' in rule.varargs:
            return FILE_TYPE_RULES_NAME, False
        elif isinstance(rule.parts[0], str):
            if rule.parts[0].endswith('_prop'):
                return PROPERTY_RULES_NAME, False
            elif rule.parts[0].endswith('_hwservice'):
                return HWSERVICE_TYPE_RULES_NAME, False
            elif rule.parts[0].endswith('_service'):
                return SERVICE_TYPE_RULES_NAME, False

        return None, False
    elif rule.rule_type in set(
        [
            RuleType.ATTRIBUTE.value,
            RuleType.EXPANDATTRIBUTE.value,
            'hal_attribute',
        ]
    ):
        return ATTRIBUTE_RULES_NAME, True
    elif isinstance(rule.parts[0], str):
        if rule.parts[0].endswith('_prop'):
            return PROPERTY_RULES_NAME, False

    return None, False


def group_rules(rules: RuleContainer):
    # Group rules based on main type
    grouped_rules: Dict[str, Set[Rule]] = {}
    for rule in rules:
        name = domain_type(rule)

        if name not in grouped_rules:
            grouped_rules[name] = set()

        grouped_rules[name].add(rule)

    # Re-group simple rules into common files
    regrouped_rules: Dict[str, Set[Rule]] = {}
    for name, group in grouped_rules.items():
        # If all rules of this group are simple, re-group them
        is_all_simple_type = True
        simple_type_names: List[Optional[str]] = []
        force_in_simple_types: List[bool] = []
        for rule in group:
            simple_type_name, force_in_simple_type = rule_simple_type_name(rule)
            simple_type_names.append(simple_type_name)
            force_in_simple_types.append(force_in_simple_type)

            if simple_type_name is None:
                is_all_simple_type = False

        for new_name, force_in_simple_type, rule in zip(
            simple_type_names,
            force_in_simple_types,
            group,
        ):
            group_name = name
            if is_all_simple_type or force_in_simple_type:
                assert new_name is not None
                group_name = new_name

            if group_name not in regrouped_rules:
                regrouped_rules[group_name] = set()

            regrouped_rules[group_name].add(rule)

    return regrouped_rules


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
            RuleType.ALLOW.value
            | RuleType.NEVERALLOW.value
            | RuleType.AUDITALLOW.value
            | RuleType.DONTAUDIT.value
            | RuleType.ALLOWXPERM.value
            | RuleType.NEVERALLOWXPERM.value
            | RuleType.AUDITALLOWXPERM.value
            | RuleType.DONTAUDITXPERM.value
            | RuleType.TYPE_TRANSITION.value
        ):
            handle_type(rule.parts[0])
            handle_type(rule.parts[1])
        case RuleType.GENFSCON.value:
            handle_type(rule.parts[2])
        case RuleType.TYPE.value | RuleType.TYPEATTRIBUTE.value:
            pass
        case RuleType.ATTRIBUTE.value | RuleType.EXPANDATTRIBUTE.value:
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
    if rule.rule_type != RuleType.TYPE.value:
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


def rule_macro_sort_key(rule: Rule):
    key = rule_sort_key(rule)

    if not rule.is_macro:
        min_order = rule_type_order(rule)
        return (min_order, key)

    min_order = 0

    assert rule.expanded_rules is not None
    for r in rule.expanded_rules:
        order = rule_type_order(r)
        if order < min_order:
            min_order = order

    return (min_order, key)


def enforce_type_decl_order(rules: List[Rule]):
    type_rules: Dict[str, Rule] = {}

    for rule in rules:
        for t in rule_defined_types(rule):
            type_rules[t] = rule

    emitted: Set[Rule] = set()
    result: List[Rule] = []

    def emit(rule: Rule):
        if rule in emitted:
            return

        for t in sorted(rule_used_types(rule)):
            dep = type_rules.get(t)
            if dep is not None and dep != rule:
                emit(dep)

        emitted.add(rule)
        result.append(rule)

    for rule in rules:
        emit(rule)

    return result


def output_grouped_rules(
    grouped_rules: Dict[str, Set[Rule]],
    source: Source,
    output_dir: Path,
):
    for name, rules in grouped_rules.items():
        sorted_rules = sorted(
            rules,
            key=rule_macro_sort_key,
        )

        sorted_rules = enforce_type_decl_order(sorted_rules)

        output_path = output_dir / name
        with open(output_path, 'w') as o:
            last_type = None
            for rule in sorted_rules:
                if last_type is not None and rule.rule_type != last_type:
                    o.write('\n')
                last_type = rule.rule_type
                o.write(
                    rule.format(
                        class_perms=source.macros.class_perms,
                        ioctls=source.macros.ioctls,
                        ioctl_defines=source.macros.ioctl_defines,
                        nlmsgs=source.macros.nlmsgs,
                        nlmsg_defines=source.macros.nlmsg_defines,
                    )
                )
                o.write('\n')

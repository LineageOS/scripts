# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import re
from functools import cache
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from sepolicy.match import merge_class_sets
from sepolicy.rule import (
    Rule,
    RuleType,
    rule_defined_types,
    rule_type_order,
    rule_used_types,
)
from sepolicy.rule_container import RuleContainer
from sepolicy.source_macros import SourceMacros
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
    if rule.rule_type == RuleType.TYPE:
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
            RuleType.ATTRIBUTE,
            RuleType.EXPANDATTRIBUTE,
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


def rule_macro_sort_key(rule_formatted: Tuple[Rule, str]):
    rule, formatted = rule_formatted

    if not rule.is_macro:
        min_order = rule_type_order(rule)
        return (min_order, formatted)

    min_order = 0

    assert rule.expanded_rules is not None
    for r in rule.expanded_rules:
        order = rule_type_order(r)
        if order < min_order:
            min_order = order

    return (min_order, formatted)


def enforce_type_decl_order(rules_formatted: List[Tuple[Rule, str]]):
    type_rules: Dict[str, Tuple[Rule, str]] = {}

    for rf in rules_formatted:
        rule, _ = rf
        for t in rule_defined_types(rule):
            type_rules[t] = rf

    emitted: Set[Rule] = set()
    result: List[Tuple[Rule, str]] = []

    def emit(rf: Tuple[Rule, str]):
        rule, _ = rf
        if rule in emitted:
            return

        for t in sorted(rule_used_types(rule)):
            dep = type_rules.get(t)
            if dep is not None and dep[0] != rule:
                emit(dep)

        emitted.add(rule)
        result.append(rf)

    for rf in rules_formatted:
        emit(rf)

    return result


def render_grouped_rules(
    grouped_rules: Dict[str, Set[Rule]],
    macros: Optional[SourceMacros],
    guard: Optional[str] = None,
) -> Dict[str, str]:
    class_perms = None
    class_sets = None
    ioctls = None
    ioctl_defines = None
    nlmsgs = None
    nlmsg_defines = None
    if macros is not None:
        class_perms = macros.class_perms
        class_sets = macros.class_sets
        ioctls = macros.ioctls
        ioctl_defines = macros.ioctl_defines
        nlmsgs = macros.nlmsgs
        nlmsg_defines = macros.nlmsg_defines

    rendered: Dict[str, str] = {}
    for name, rules in sorted(grouped_rules.items()):
        if class_sets is not None:
            rules = RuleContainer(rules)
            merge_class_sets(rules, class_sets)

        rules_formatted = (
            (
                r,
                r.format(
                    class_perms=class_perms,
                    ioctls=ioctls,
                    ioctl_defines=ioctl_defines,
                    nlmsgs=nlmsgs,
                    nlmsg_defines=nlmsg_defines,
                ),
            )
            for r in rules
        )
        sorted_rules = sorted(
            rules_formatted,
            key=rule_macro_sort_key,
        )

        sorted_rules = enforce_type_decl_order(sorted_rules)

        parts: List[str] = []
        if guard:
            parts.append(f'{guard}(`\n\n')
        last_type = None
        for rule, formatted in sorted_rules:
            if last_type is not None and rule.rule_type != last_type:
                parts.append('\n')
            last_type = rule.rule_type
            parts.append(formatted)
            parts.append('\n')
        if guard:
            parts.append("\n')\n")
        rendered[name] = ''.join(parts)

    return rendered


def output_grouped_rules(
    grouped_rules: Dict[str, Set[Rule]],
    macros: Optional[SourceMacros],
    output_dir: Path,
    guard: Optional[str] = None,
):
    rendered = render_grouped_rules(grouped_rules, macros, guard)
    for name, text in rendered.items():
        output_path = output_dir / name
        with open(output_path, 'w') as o:
            o.write(text)

# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import re
from collections import Counter, defaultdict
from functools import cache
from pathlib import Path
from typing import DefaultDict, Dict, List, Optional, Set, Tuple

from sepolicy.match import merge_class_sets, merge_typeattribute_rules
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

ATTRIBUTE_RULE_TYPES = (RuleType.ATTRIBUTE, RuleType.EXPANDATTRIBUTE)

DECLARATION_RULE_TYPES = (
    RuleType.TYPE,
    RuleType.TYPEATTRIBUTE,
    RuleType.ATTRIBUTE,
    RuleType.EXPANDATTRIBUTE,
    RuleType.GENFSCON,
)


def rule_domain_type(rule: Rule) -> Optional[str]:
    domain = rule.parts[0]
    if not isinstance(domain, str) and len(rule.parts) >= 2:
        domain = rule.parts[1]

    if not isinstance(domain, str):
        return None

    return domain


def domain_file_name(domain: Optional[str]):
    if domain is None:
        return LEFTOVER_RULES_NAME

    t = extract_domain_type(domain)
    return f'{t}.te'


def is_attribute_rule(rule: Rule) -> bool:
    if rule.rule_type in ATTRIBUTE_RULE_TYPES:
        return True

    if not rule.is_macro:
        return False

    assert rule.expanded_rules is not None

    for r in rule.expanded_rules:
        if r.rule_type in ATTRIBUTE_RULE_TYPES:
            return True

    return False


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
    elif is_attribute_rule(rule):
        return ATTRIBUTE_RULES_NAME, True
    elif isinstance(rule.parts[0], str):
        if rule.parts[0].endswith('_prop'):
            return PROPERTY_RULES_NAME, False

    return None, False


def type_usage_owner(
    rule: Rule,
    usage_files: Dict[str, Set[str]],
    rule_domains: Set[str],
):
    if rule.rule_type != RuleType.TYPE:
        return None

    for defined in rule_defined_types(rule):
        if defined in rule_domains:
            return None

        files = usage_files.get(defined)
        if files and len(files) == 1:
            return next(iter(files))

    return None


def group_rules(
    rules: RuleContainer,
    rule_guard: Optional[Dict[Rule, str]] = None,
):
    rules = RuleContainer(rules)
    merge_typeattribute_rules(rules, rule_guard)

    domain_files: DefaultDict[str, Counter[str]] = defaultdict(Counter)
    for rule in rules:
        domain = rule_domain_type(rule)
        if domain is None:
            continue

        for mark in rules.marks(rule):
            file_name = Path(mark.path).name
            domain_files[domain][file_name] += 1

    domain_file: Dict[str, str] = {}
    for domain, files in domain_files.items():
        name = max(
            files,
            key=lambda f: (
                # Sort by number of rules for this domain using this file
                files[f],
                # Alphabetically, to preserve a stable order
                f,
            ),
        )

        if name.endswith('.te'):
            domain_file[domain] = name

    usage_files: DefaultDict[str, Set[str]] = defaultdict(set)
    rule_domains: Set[str] = set()
    for rule in rules:
        if rule.rule_type not in DECLARATION_RULE_TYPES and isinstance(
            rule.parts[0], str
        ):
            rule_domains.add(rule.parts[0])

        te_files: Set[str] = set()
        for mark in rules.marks(rule):
            file_name = Path(mark.path).name
            if file_name.endswith('.te'):
                te_files.add(file_name)

        if not te_files:
            continue

        for used in rule_used_types(rule):
            usage_files[used].update(te_files)

    grouped_rules: Dict[str, Set[Rule]] = {}
    for rule in rules:
        domain = rule_domain_type(rule)
        name = None
        if domain is not None:
            name = domain_file.get(domain)
        if name is None:
            name = type_usage_owner(rule, usage_files, rule_domains)
        if name is None:
            name = domain_file_name(domain)

        if name not in grouped_rules:
            grouped_rules[name] = set()

        grouped_rules[name].add(rule)

    # Re-group simple rules into common files
    regrouped_rules: Dict[str, Set[Rule]] = {}
    for name, group in grouped_rules.items():
        simple_names = {rule: rule_simple_type_name(rule) for rule in group}
        all_simple = all(n is not None for n, _ in simple_names.values())
        for rule, (simple_name, force) in simple_names.items():
            group_name = simple_name if all_simple or force else name
            assert group_name is not None
            regrouped_rules.setdefault(group_name, set()).add(rule)

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
    rule_guard: Optional[Dict[Rule, str]] = None,
    mark_source: Optional[RuleContainer] = None,
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

    if rule_guard is None:
        rule_guard = {}

    rendered: Dict[str, str] = {}
    for name, rules in sorted(grouped_rules.items()):
        by_guard: Dict[Optional[str], List[Rule]] = defaultdict(list)
        for rule in rules:
            by_guard[rule_guard.get(rule)].append(rule)

        file_guard: Dict[Rule, str] = {}
        file_rules: List[Rule] = []
        for guard_name, group in by_guard.items():
            merged = RuleContainer(group)
            if class_sets is not None:
                merge_class_sets(merged, class_sets, mark_source)
            for rule in merged:
                file_rules.append(rule)
                if guard_name is not None:
                    file_guard[rule] = guard_name

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
            for r in file_rules
        )
        sorted_rules = sorted(
            rules_formatted,
            key=lambda rf, fg=file_guard: (
                rule_macro_sort_key(rf)[0],
                fg.get(rf[0]) or '',
                rf[1],
            ),
        )

        sorted_rules = enforce_type_decl_order(sorted_rules)

        parts: List[str] = []
        active_guard: Optional[str] = None
        last_type = None
        for rule, formatted in sorted_rules:
            this_guard = file_guard.get(rule)
            if this_guard != active_guard:
                if active_guard is not None:
                    parts.append("')\n")
                if parts:
                    parts.append('\n')
                if this_guard is not None:
                    parts.append(f'{this_guard}(`\n')
                active_guard = this_guard
                last_type = None
            if last_type is not None and rule.rule_type != last_type:
                parts.append('\n')
            last_type = rule.rule_type
            parts.append(formatted)
            parts.append('\n')
        if active_guard is not None:
            parts.append("')\n")
        rendered[name] = ''.join(parts)

    return rendered


def output_grouped_rules(
    grouped_rules: Dict[str, Set[Rule]],
    macros: Optional[SourceMacros],
    output_dir: Path,
    rule_guard: Optional[Dict[Rule, str]] = None,
    mark_source: Optional[RuleContainer] = None,
):
    rendered = render_grouped_rules(
        grouped_rules,
        macros,
        rule_guard,
        mark_source,
    )
    for name, text in rendered.items():
        output_path = output_dir / name
        with open(output_path, 'w') as o:
            o.write(text)

# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import re
from functools import cache
from pathlib import Path
from typing import Dict, List, Optional, Set

from sepolicy.rule import Rule, RuleType, rule_sort_key
from utils.mld import MultiLevelDict

VENDOR_PREFIX = 'vendor_'
PROPERTY_CONTEXTS_NAME = 'property_contexts'
FILE_CONTEXTS_NAME = 'file_contexts'
HWSERVICE_CONTEXTS_NAME = 'hwservice_contexts'
VNDSERVICE_CONTEXTS_NAME = 'vndservice_contexts'
SERVICE_CONTEXTS_NAME = 'service_contexts'
SEAPP_CONTEXTS_NAME = 'seapp_contexts'
GENFS_CONTEXTS_NAME = 'genfs_contexts'


def copy_contexts(input_path: str, output_path: str):
    # TODO: align parts against eachother?

    lines: List[str] = []
    with open(input_path, 'r') as file:
        for line in file.readlines():
            line = line.strip()

            if not line:
                continue

            if line.startswith('#'):
                continue

            line = re.sub(r'\s+', ' ', line)
            lines.append(line)

    lines.sort()

    with open(output_path, 'w') as file:
        for line in lines:
            file.write(line)
            file.write('\n')


def output_contexts(selinux_dir: Optional[str], output_dir: str):
    if selinux_dir is None:
        return

    for name in [
        PROPERTY_CONTEXTS_NAME,
        FILE_CONTEXTS_NAME,
        HWSERVICE_CONTEXTS_NAME,
        VNDSERVICE_CONTEXTS_NAME,
        SERVICE_CONTEXTS_NAME,
        SEAPP_CONTEXTS_NAME,
    ]:
        input_path = Path(selinux_dir, name)
        if not input_path.exists():
            input_path = Path(selinux_dir, f'{VENDOR_PREFIX}{name}')

        if not input_path.exists():
            continue

        output_path = Path(output_dir, name)
        copy_contexts(str(input_path), str(output_path))


def output_genfs_contexts(genfs_rules: List[Rule], output_dir: str):
    output_path = Path(output_dir, GENFS_CONTEXTS_NAME)
    with open(output_path, 'w') as o:
        for rule in genfs_rules:
            o.write(str(rule))
            o.write('\n')


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
        if 'dev_type' in rule.varargs:
            return DEVICE_TYPE_RULES_NAME
        elif 'file_type' in rule.varargs or 'fs_type' in rule.varargs:
            return FILE_TYPE_RULES_NAME
        elif isinstance(rule.parts[0], str):
            if rule.parts[0].endswith('_prop'):
                return PROPERTY_RULES_NAME
            elif rule.parts[0].endswith('_hwservice'):
                return HWSERVICE_TYPE_RULES_NAME
            elif rule.parts[0].endswith('_service'):
                return SERVICE_TYPE_RULES_NAME

        return None
    elif rule.rule_type in set(
        [
            RuleType.ATTRIBUTE.value,
            RuleType.EXPANDATTRIBUTE.value,
            'hal_attribute',
        ]
    ):
        return ATTRIBUTE_RULES_NAME
    elif isinstance(rule.parts[0], str):
        if rule.parts[0].endswith('_prop'):
            return PROPERTY_RULES_NAME

    return None


def group_rules(mld: MultiLevelDict[Rule]):
    # Group rules based on main type
    grouped_rules: Dict[str, Set[Rule]] = {}
    for rule in mld.walk():
        name = domain_type(rule)

        if name not in grouped_rules:
            grouped_rules[name] = set()

        grouped_rules[name].add(rule)

    # Re-group simple rules into common files
    regrouped_rules: Dict[str, Set[Rule]] = {}
    for name, rules in grouped_rules.items():
        # If all rules of this group are simple, re-group them
        is_all_simple_type = True
        simple_type_names: List[Optional[str]] = []
        for rule in rules:
            simple_type_name = rule_simple_type_name(rule)
            simple_type_names.append(simple_type_name)

            if simple_type_name is None:
                is_all_simple_type = False

        for new_name, rule in zip(simple_type_names, rules):
            if is_all_simple_type:
                assert new_name is not None
                name = new_name

            if name not in regrouped_rules:
                regrouped_rules[name] = set()

            regrouped_rules[name].add(rule)

    return regrouped_rules


def output_grouped_rules(grouped_rules: Dict[str, Set[Rule]], output_dir: str):
    for name, rules in grouped_rules.items():
        sorted_rules = sorted(rules, key=rule_sort_key)

        output_path = Path(output_dir, name)
        with open(output_path, 'w') as o:
            last_type = None
            for rule in sorted_rules:
                if last_type is not None and rule.rule_type != last_type:
                    o.write('\n')
                last_type = rule.rule_type
                o.write(str(rule))
                o.write('\n')

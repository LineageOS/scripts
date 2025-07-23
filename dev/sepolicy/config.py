# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

# Variables extracted from system/sepolicy/build/soong/policy.go

from __future__ import annotations

from typing import Dict, Tuple

from sepolicy.conditional_type import ConditionalType
from sepolicy.match import rule_match_keys
from sepolicy.match_extract import rule_extract_part_iter
from sepolicy.rule import Rule, RuleType
from utils.mld import MultiLevelDict
from utils.utils import Color, color_print

default_variables = {
    # MlsSens = 1
    'mls_num_sens': '1',
    # MlsCats = 1024
    'mls_num_cats': '1024',
    # TARGET_ARCH
    'target_arch': 'arm64',
    'target_with_asan': 'false',
    # WITH_DEXPREOPT
    'target_with_dexpreopt': 'false',
    'target_with_native_coverage': 'false',
    # TARGET_BUILD_VARIANT
    'target_build_variant': 'user',
    'target_full_treble': 'true',
    'target_compatible_property': 'true',
    # BUILD_BROKEN_TREBLE_SYSPROP_NEVERALLOW
    'target_treble_sysprop_neverallow': 'true',
    # BUILD_BROKEN_ENFORCE_SYSPROP_OWNER
    'target_enforce_sysprop_owner': 'true',
    'target_exclude_build_test': 'false',
    # PRODUCT_REQUIRES_INSECURE_EXECMEM_FOR_SWIFTSHADER
    'target_requires_insecure_execmem_for_swiftshader': 'false',
    # PRODUCT_SET_DEBUGFS_RESTRICTIONS
    'target_enforce_debugfs_restriction': 'true',
    'target_recovery': 'false',
    # BOARD_API_LEVEL
    'target_board_api_level': '202404',
}

default_variables_match_rules: Dict[
    str,
    Tuple[Rule, str, str],
] = {
    # public/te_macros
    # crash_dump_fallback()
    # allow $1 su:fifo_file append;
    'target_build_variant': (
        Rule(
            RuleType.ALLOW.value,
            (
                'allow',
                '$1',
                'su',
                'fifo_file',
            ),
            ('append',),
        ),
        'userdebug',
        'user',
    ),
    # public/te_macros
    # hal_client_domain()
    # allow $2 vendor_file:file { read open getattr execute map };
    'target_full_treble': (
        Rule(
            RuleType.ALLOW.value,
            (
                '$2',
                'vendor_file',
                'file',
            ),
            (
                'read',
                'getattr',
                'map',
                'execute',
                'open',
            ),
        ),
        'false',
        'true',
    ),
    # public/te_macros
    # vendor_restricted_prop()
    # ->
    # neverallow { coredomain -init } $1:property_service set;
    'target_treble_sysprop_neverallow': (
        Rule(
            RuleType.NEVERALLOW.value,
            (
                ConditionalType(
                    ['coredomain'],
                    ['init'],
                    False,
                ),
                '$1',
                'property_service',
            ),
            ('set',),
        ),
        'true',
        'false',
    ),
    # public/te_macros
    # hal_attribute_hwservice()
    # neverallow { domain -$1_client -$1_server } $2:hwservice_manager find;
    'target_exclude_build_test': (
        Rule(
            RuleType.NEVERALLOW.value,
            (
                ConditionalType(
                    ['domain'],
                    ['$1_client', '$1_server'],
                    False,
                ),
                '$2',
                'hwservice_manager',
            ),
            ('find',),
        ),
        'false',
        'true',
    ),
}


def get_default_variables(mld: MultiLevelDict[Rule]):
    variables: Dict[str, str] = default_variables.copy()

    for variable_name, data in default_variables_match_rules.items():
        rule, match_value, pass_value = data

        match_keys = rule_match_keys(rule, False)

        found = False
        for matched_rule in mld.match(match_keys):
            args_values = rule_extract_part_iter(
                rule.parts,
                matched_rule.parts,
            )

            if args_values is not None:
                found = True
                break

        if found:
            variables[variable_name] = match_value
        else:
            variables[variable_name] = pass_value

        color_print(
            f'Found variable {variable_name}={variables[variable_name]}',
            color=Color.GREEN,
        )

    return variables

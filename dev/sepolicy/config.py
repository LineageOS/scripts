# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

# Variables extracted from system/sepolicy/build/soong/policy.go

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from sepolicy.conditional_type import ConditionalType
from sepolicy.rule import Rule, RuleType, rule_hash_value
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
    'target_exclude_build_test': 'true',
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
    Tuple[List[Optional[rule_hash_value]], str, str],
] = {
    # TODO: fix
    # public/file.te
    # type asanwrapper_exec, exec_type, file_type;
    # type rules are compiled into typeattributeset and then split by us into
    # typeattribute
    'target_with_asan': (
        [
            RuleType.TYPEATTRIBUTE.value,
            'asanwrapper_exec',
            'exec_type',
            frozenset(),
        ],
        'true',
        'false',
    ),
    # TODO: fix
    # public/domain.te
    # allow domain method_trace_data_file:dir create_dir_perms;
    'target_with_native_coverage': (
        [
            RuleType.ALLOW.value,
            'domain',
            'method_trace_data_file',
            'dir',
            # TODO: Try to extract the value of create_dir_perms automatically.
            # Currently it is not possible to extract these automatically because
            # the variables that we're trying to autodetect here need to be passed
            # to m4 for variable expansion, and the create_dir_perms macro is parsed
            # from the m4 result
            frozenset(
                [
                    'open',
                    'getattr',
                    'lock',
                    'watch',
                    'write',
                    'watch_reads',
                    'rmdir',
                    'reparent',
                    'ioctl',
                    'remove_name',
                    'add_name',
                    'create',
                    'rename',
                    'setattr',
                    'read',
                    'search',
                ]
            ),
        ],
        'true',
        'false',
    ),
    # TODO: fix
    # public/domain.te
    # allow domain su:fd use;
    'target_build_variant': (
        [
            RuleType.ALLOW.value,
            'allow',
            'domain',
            'su',
            'fd',
            frozenset(['use']),
        ],
        'userdebug',
        'user',
    ),
    # public/te_macros
    # hal_client_domain:
    # allow $2 vendor_file:file { read open getattr execute map };
    'target_full_treble': (
        [
            RuleType.ALLOW.value,
            None,
            'vendor_file',
            'file',
            frozenset(
                [
                    'read',
                    'getattr',
                    'map',
                    'execute',
                    'open',
                ]
            ),
        ],
        'false',
        'true',
    ),
    # TODO: improve
    # public/property.te
    # vendor_internal_prop:
    # ->
    # type vendor_default_prop, property_type, vendor_property_type, vendor_internal_property_type;
    'target_compatible_property': (
        [
            RuleType.TYPEATTRIBUTE.value,
            'vendor_default_prop',
            'vendor_internal_property_type',
            frozenset(),
        ],
        'true',
        'false',
    ),
    # public/te_macros
    # vendor_restricted_prop(build_prop)
    # ->
    # neverallow { coredomain -init } $1:property_service set;
    'target_treble_sysprop_neverallow': (
        [
            RuleType.NEVERALLOW.value,
            ConditionalType(
                ['coredomain'],
                ['init'],
                False,
            ),
            None,
            'property_service',
            frozenset(['set']),
        ],
        'true',
        'false',
    ),
}


def get_default_variables(mld: MultiLevelDict[Rule]):
    variables: Dict[str, str] = default_variables.copy()

    for variable_name, data in default_variables_match_rules.items():
        match_keys, match_value, pass_value = data

        found = False
        for _ in mld.match(match_keys):
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

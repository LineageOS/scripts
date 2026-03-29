#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set, Tuple

from sepolicy.contexts import ContextsType, resolve_contexts_paths

# From system/sepolicy/flagging/Android.bp
NEEDED_BUILD_FLAGS = {
    'RELEASE_AVF_SUPPORT_CUSTOM_VM_WITH_PARAVIRTUALIZED_DEVICES',
    'RELEASE_AVF_ENABLE_EARLY_VM',
    'RELEASE_AVF_ENABLE_DEVICE_ASSIGNMENT',
    'RELEASE_AVF_ENABLE_LLPVM_CHANGES',
    'RELEASE_AVF_ENABLE_NETWORK',
    'RELEASE_AVF_ENABLE_MICROFUCHSIA',
    'RELEASE_AVF_ENABLE_VM_TO_TEE_SERVICES_ALLOWLIST',
    'RELEASE_AVF_ENABLE_WIDEVINE_PVM',
    'RELEASE_RANGING_STACK',
    'RELEASE_READ_FROM_NEW_STORAGE',
    'RELEASE_SUPERVISION_SERVICE',
    'RELEASE_HARDWARE_BLUETOOTH_RANGING_SERVICE',
    'RELEASE_UNLOCKED_STORAGE_API',
    'RELEASE_BLUETOOTH_SOCKET_SERVICE',
    'RELEASE_SEPOLICY_RESTRICT_KERNEL_KEYRING_SEARCH',
    'RELEASE_TELEPHONY_MODULE',
}


@dataclass(frozen=True)
class PolicyInfo:
    contexts_file_paths: Dict[ContextsType, List[Path]]
    extra_rules_paths: List[Tuple[str, Path]]
    public_rules_paths: List[Tuple[str, Path]]
    policy_path: Path
    version: str
    partition_name: str
    variables: Dict[str, str]


def get_build_prop(lines: List[str], prop_name: str):
    prop_name_eq = f'{prop_name}='

    for line in lines:
        if line.startswith(prop_name_eq):
            return line[len(prop_name_eq) :]

    assert False, f'Failed to find build prop: {prop_name}'


def get_sdk_value(build_prop_lines: List[str]):
    sdk_value_str = get_build_prop(build_prop_lines, 'ro.build.version.sdk')

    # TODO: find the proper value
    if sdk_value_str == '36':
        return '202504'
    elif sdk_value_str == '35':
        return '202404'

    return f'{sdk_value_str}.0'


def get_build_flags(
    build_flags_text: str,
    build_flags: Set[str],
    variables: Dict[str, str],
):
    build_flags_data = json.loads(build_flags_text)
    flags = build_flags_data['flags']

    for flag in flags:
        flag_name = flag['flag_declaration']['name']
        if flag_name not in build_flags:
            continue

        flag_value = flag['flag_declaration']['value']['Val']
        bool_value = flag_value.get('BoolValue')
        string_value = flag_value.get('StringValue')

        if bool_value is not None:
            value = str(bool_value).lower()
        elif string_value is not None:
            value = string_value
        else:
            assert False, json.dumps(flag)

        variables[f'target_flag_{flag_name}'] = value


def get_selinux_dir_policy(selinux_dir: Path, verbose: bool):
    partition_root = selinux_dir.parent.parent
    partition_name = partition_root.name
    dump_root = partition_root.parent

    vendor_policy_path = Path(dump_root, 'vendor/etc/selinux')
    system_policy_path = Path(dump_root, 'system/etc/selinux')

    platform_build_prop_path = Path(dump_root, 'system/build.prop')
    platform_build_prop_text = platform_build_prop_path.read_text()
    platform_build_prop_lines = platform_build_prop_text.splitlines()
    platform_policy_version = get_sdk_value(platform_build_prop_lines)

    vendor_build_prop_path = Path(dump_root, 'vendor/build.prop')
    vendor_build_prop_text = vendor_build_prop_path.read_text()
    vendor_build_prop_lines = vendor_build_prop_text.splitlines()
    vendor_board_api_level = get_build_prop(
        vendor_build_prop_lines,
        'ro.board.api_level',
    )
    target_arch = get_build_prop(
        vendor_build_prop_lines,
        'ro.bionic.arch',
    )

    contexts_file_paths = resolve_contexts_paths(
        [selinux_dir],
        partition_name,
        None,
        verbose,
    )

    # Read policy for vendor / odm
    # For system / system_ext / product, this is used to find public
    # types
    # For vendor / odm, this is loaded to allow proper macro resolution
    versioned_platform_policy_path = Path(
        vendor_policy_path,
        'plat_pub_versioned.cil',
    )
    assert versioned_platform_policy_path.exists(), (
        versioned_platform_policy_path
    )

    platform_policy_path = Path(
        system_policy_path,
        'plat_sepolicy.cil',
    )
    assert platform_policy_path.exists(), platform_policy_path

    if partition_name in ['vendor', 'odm']:
        extra_rules_paths = [
            (vendor_board_api_level, versioned_platform_policy_path),
        ]
        referencing_rules_paths = []
        policy_version = vendor_board_api_level
    else:
        extra_rules_paths = [
            (platform_policy_version, platform_policy_path),
        ]
        referencing_rules_paths = [
            (vendor_board_api_level, versioned_platform_policy_path),
        ]
        policy_version = platform_policy_version

    if partition_name == 'system':
        partition_name = 'plat'
        platform_policy_path = None

    policy_path = Path(selinux_dir, f'{partition_name}_sepolicy.cil')

    assert policy_path.exists(), policy_path

    #
    # Gather all variables needed for conditional
    #
    variables: Dict[str, str] = {}

    build_flags_path = Path(dump_root, partition_name, 'etc/build_flags.json')
    build_flags_text = build_flags_path.read_text()
    get_build_flags(build_flags_text, NEEDED_BUILD_FLAGS, variables)

    #
    # From system/sepolicy/buid/soong/policy.go
    #

    # MlsSens = 1
    variables['mls_num_sens'] = '1'

    # MlsCats = 1024
    variables['mls_num_cats'] = '1024'

    # TARGET_ARCH
    variables['target_arch'] = target_arch

    # WITH_DEXPREOPT
    variables['target_with_dexpreopt'] = 'false'

    # CLANG_COVERAGE or NATIVE_COVERAGE
    variables['target_with_native_coverage'] = 'false'

    # TODO: set to false for recovery
    variables['target_full_treble'] = 'true'

    # TODO: set to false for recovery
    variables['target_compatible_property'] = 'true'

    # TODO: set to false for recovery, allow for parsing from user
    # BUILD_BROKEN_TREBLE_SYSPROP_NEVERALLOW
    variables['target_treble_sysprop_neverallow'] = 'true'

    # TODO: set to false for recovery, allow for parsing from user
    # BUILD_BROKEN_ENFORCE_SYSPROP_OWNER
    variables['target_enforce_sysprop_owner'] = 'true'

    # Set to true for CTS only
    variables['target_exclude_build_test'] = 'false'

    # PRODUCT_REQUIRES_INSECURE_EXECMEM_FOR_SWIFTSHADER
    variables['target_requires_insecure_execmem_for_swiftshader'] = 'false'

    # PRODUCT_SET_DEBUGFS_RESTRICTIONS
    variables['target_enforce_debugfs_restriction'] = 'true'

    # TODO: set to true for recovery
    variables['target_recovery'] = 'false'

    # BOARD_API_LEVEL
    variables['target_board_api_level'] = policy_version

    try:
        build_type = get_build_prop(platform_build_prop_lines, 'ro.build.type')
        # TARGET_BUILD_VARIANT
        variables['target_build_variant'] = build_type
    except AssertionError:
        pass

    try:
        get_build_prop(platform_build_prop_lines, 'ro.sanitize.address')
        variables['target_with_asan'] = 'true'
    except AssertionError:
        pass

    return PolicyInfo(
        contexts_file_paths=contexts_file_paths,
        extra_rules_paths=extra_rules_paths,
        public_rules_paths=referencing_rules_paths,
        policy_path=policy_path,
        version=policy_version,
        partition_name=partition_name,
        variables=variables,
    )

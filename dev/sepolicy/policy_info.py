#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

from sepolicy.contexts import ContextsType, resolve_contexts_paths


@dataclass(frozen=True)
class PolicyInfo:
    contexts_file_paths: Dict[ContextsType, List[Path]]
    extra_rules_paths: List[Tuple[str, Path]]
    public_rules_paths: List[Tuple[str, Path]]
    policy_path: Path
    version: str
    partition_name: str


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

    vendor_build_prop_path = Path(dump_root, 'vendor/etc/build.prop')
    vendor_build_prop_text = vendor_build_prop_path.read_text()
    vendor_build_prop_lines = vendor_build_prop_text.splitlines()
    vendor_board_api_level = get_build_prop(
        vendor_build_prop_lines,
        'ro.board.api_level',
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

    return PolicyInfo(
        contexts_file_paths=contexts_file_paths,
        extra_rules_paths=extra_rules_paths,
        public_rules_paths=referencing_rules_paths,
        policy_path=policy_path,
        version=policy_version,
        partition_name=partition_name,
    )

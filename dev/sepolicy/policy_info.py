#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class PolicyInfo:
    path: Path
    platform_policy_path: Optional[Path]
    policy_path: Path
    version: str
    partition_name: str
    split_public_private: bool
    referencing_policy_path: Optional[Path]
    referencing_policy_version: Optional[str]


def get_sdk_value(build_prop_path: Path):
    SDK_PROP = 'ro.build.version.sdk='
    sdk_value_str: Optional[str] = None

    for line in build_prop_path.read_text().splitlines():
        if line.startswith(SDK_PROP):
            sdk_value_str = line[len(SDK_PROP) :]

    if sdk_value_str is None:
        return None

    # TODO: find the proper value
    if sdk_value_str == '36':
        return '202504'
    elif sdk_value_str == '35':
        return '202404'

    return f'{sdk_value_str}.0'


def get_selinux_dir_policy(selinux_dir: Path):
    partition_root = selinux_dir.parent.parent
    partition_name = partition_root.name
    dump_root = partition_root.parent

    vendor_policy_path = Path(dump_root, 'vendor/etc/selinux')
    system_policy_path = Path(dump_root, 'system/etc/selinux')
    platform_build_prop_path = Path(dump_root, 'system/build.prop')

    split_public_private = False
    referencing_policy_path = None
    referencing_policy_version = None

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

    # Read policy version for vendor / odm
    versioned_platform_policy_version_path = Path(
        vendor_policy_path,
        'plat_sepolicy_vers.txt',
    )
    assert versioned_platform_policy_version_path.exists(), (
        versioned_platform_policy_version_path
    )
    versioned_platform_policy_version = (
        versioned_platform_policy_version_path.read_text().strip()
    )

    if partition_name in ['vendor', 'odm']:
        platform_policy_path = versioned_platform_policy_path
        policy_version = versioned_platform_policy_version
    else:
        platform_policy_path = Path(
            system_policy_path,
            'plat_sepolicy.cil',
        )
        assert platform_policy_path.exists(), platform_policy_path

        policy_version = get_sdk_value(platform_build_prop_path)

        split_public_private = True
        referencing_policy_path = versioned_platform_policy_path
        referencing_policy_version = versioned_platform_policy_version

    if partition_name == 'system':
        partition_name = 'plat'
        platform_policy_path = None

    policy_path = Path(selinux_dir, f'{partition_name}_sepolicy.cil')

    assert policy_path.exists(), policy_path
    assert policy_version is not None

    return PolicyInfo(
        path=selinux_dir,
        platform_policy_path=platform_policy_path,
        policy_path=policy_path,
        version=policy_version,
        partition_name=partition_name,
        split_public_private=split_public_private,
        referencing_policy_path=referencing_policy_path,
        referencing_policy_version=referencing_policy_version,
    )

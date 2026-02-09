# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Dict, List, Optional

from bp.bp_module import BpModule

ANDROID_BP_NAME = 'Android.bp'
ANDROID_BP_COPYRIGHT = """
//
// SPDX-FileCopyrightText: The LineageOS Project
// SPDX-License-Identifier: Apache-2.0
//
""".lstrip()


def merge_bp_module_defaults(base: BpModule, override: BpModule):
    result = base.copy()

    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], list)
            and isinstance(value, list)
        ):
            result[key] = result[key] + value
        else:
            result[key] = value

    return result


def bp_extend_defaults(
    module: BpModule,
    defaults: List[str],
    defaults_map: Dict[str, BpModule],
):
    base = None
    missing_defaults: List[str] = []

    for default_name in defaults:
        if default_name not in defaults_map:
            missing_defaults.append(default_name)
            continue

        defaults_module = defaults_map[default_name]

        if base is None:
            base = defaults_module
            continue

        base = merge_bp_module_defaults(base, defaults_module)

    if not base:
        return module, missing_defaults

    return merge_bp_module_defaults(base, module), missing_defaults


SPECIFIC_PARTITIONS = {
    'vendor': 'vendor',
    'device_specific': 'odm',
    'product_specific': 'product',
    'system_ext_specific': 'system_ext',
    'oem_specific': 'oem',
}

PRIORITY_PARTITIONS = [
    'system',
    'vendor',
    'odm',
    'oem',
    'product',
    'system_ext',
]


def get_partition_specific(partition: Optional[str]):
    for s, p in SPECIFIC_PARTITIONS.items():
        if partition == p:
            return s

    return None


def get_module_partition(module: BpModule):
    for s, p in SPECIFIC_PARTITIONS.items():
        if s in module:
            return p

    return 'system'


def partition_to_priority(partition: str):
    return PRIORITY_PARTITIONS.index(partition)


def write_android_bp(apk_path: str, android_bp_path: str, package: str):
    apk_path_parts = apk_path.split('/')

    partition = None
    try:
        overlay_index = apk_path_parts.index('overlay')
        partition = apk_path_parts[overlay_index - 1]
    except (ValueError, IndexError):
        pass

    specific = get_partition_specific(partition)
    if specific is None:
        specific = ''
    else:
        specific = f'\n    {specific}: true,'

    with open(android_bp_path, 'w') as o:
        o.write(
            f'''{ANDROID_BP_COPYRIGHT}
runtime_resource_overlay {{
    name: "{package}",{specific}
}}
'''
        )

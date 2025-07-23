#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from os import path

from manifest import (
    ANDROID_MANIFEST_NAME,
    parse_overlay_manifest,
    write_manifest,
)
from resources import (
    group_overlay_resources_rel_path,
    parse_overlay_resources,
    parse_package_resources,
    read_overlay_xmls,
    remove_overlay_resources,
    write_grouped_resources,
    write_overlay_xmls,
)
from target_package import get_target_package_path
from utils import Color, color_print, get_partition_specific


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
            f'''
//
// SPDX-FileCopyrightText: The LineageOS Project
// SPDX-License-Identifier: Apache-2.0
//

runtime_resource_overlay {{
    name: "{package}",{specific}
}}
'''
        )


def process_rro(overlay_path: str, output_path: str):
    manifest_path = path.join(overlay_path, ANDROID_MANIFEST_NAME)

    package, target_package, overlay_attrs = parse_overlay_manifest(
        manifest_path,
    )

    overlay_resources, overlay_xmls = parse_overlay_resources(overlay_path)
    if not overlay_resources:
        raise ValueError(f'No overlay resources in overlay {package}')

    target_package_dir, resource_dirs = get_target_package_path(target_package)
    package_resources, package_xmls = parse_package_resources(
        target_package_dir, resource_dirs
    )

    grouped_resources, missing_resources, identical_resources = (
        group_overlay_resources_rel_path(
            overlay_resources,
            package_resources,
        )
    )

    xmls, missing_xmls = read_overlay_xmls(
        overlay_path,
        overlay_xmls,
        package_xmls,
    )

    if not grouped_resources:
        raise ValueError(f'No resources left in overlay {package}')

    for xml in missing_xmls:
        color_print(
            f'XML {xml} not found in package {target_package}',
            color=Color.RED,
        )

    for resource in missing_resources:
        color_print(
            f'Resource {resource.name} not found in package {target_package}',
            color=Color.RED,
        )

    for resource in identical_resources:
        color_print(
            f'Resource {resource.name} identical in package {target_package}',
            color=Color.YELLOW,
        )

    remove_overlay_resources(overlay_path)
    write_grouped_resources(grouped_resources, overlay_path)
    write_overlay_xmls(xmls, overlay_path)

    rro_manifest_path = path.join(output_path, ANDROID_MANIFEST_NAME)
    write_manifest(
        rro_manifest_path, package, target_package, overlay_attrs
    )

    return package

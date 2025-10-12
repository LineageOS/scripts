# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from os import path

from bp.bp_utils import get_partition_specific
from rro.manifest import (
    ANDROID_MANIFEST_NAME,
    parse_overlay_manifest,
    write_manifest,
)
from rro.resources import (
    find_target_package_resources,
    group_overlay_resources_rel_path,
    parse_overlay_resources,
    read_overlay_xmls,
    remove_overlay_resources,
    write_grouped_resources,
    write_overlay_xmls,
)
from rro.target_package import get_target_packages
from utils.utils import Color, color_print
from utils.xml_utils import xml_attrib_matches


def write_rro_android_bp(
    apk_path: str,
    android_bp_path: str,
    package: str,
    aapt_raw: bool,
):
    apk_path_parts = apk_path.split('/')

    partition = None
    try:
        overlay_index = apk_path_parts.index('overlay')
        partition = apk_path_parts[overlay_index - 1]
    except (ValueError, IndexError):
        pass

    extra = ''

    specific = get_partition_specific(partition)
    if specific is not None:
        extra += f'\n    {specific}: true,'

    if aapt_raw:
        extra += '\n    aaptflags: ["--keep-raw-values"],'

    with open(android_bp_path, 'w') as o:
        o.write(
            f'''
//
// SPDX-FileCopyrightText: The LineageOS Project
// SPDX-License-Identifier: Apache-2.0
//

runtime_resource_overlay {{
    name: "{package}",{extra}
}}
'''
        )


def process_rro(overlay_path: str, output_path: str):
    manifest_path = path.join(overlay_path, ANDROID_MANIFEST_NAME)

    package, target_package, overlay_attrs = parse_overlay_manifest(
        manifest_path,
    )

    overlay_resources, overlay_xmls = parse_overlay_resources(overlay_path)
    if not overlay_resources and not overlay_xmls:
        raise ValueError(f'{package}: No resources in overlay')

    target_packages, target_package = get_target_packages(target_package)
    package_resources, package_xmls = find_target_package_resources(
        target_packages,
        overlay_resources,
        overlay_xmls,
    )

    (
        grouped_resources,
        wrong_type_resources,
        missing_resources,
        identical_resources,
    ) = group_overlay_resources_rel_path(
        overlay_resources,
        package_resources,
    )

    for resource in missing_resources:
        color_print(
            f'{package}: Resource {resource.name} not found in {target_package}',
            color=Color.RED,
        )

    for resource in identical_resources:
        color_print(
            f'{package}: Resource {resource.name} identical in {target_package}',
            color=Color.YELLOW,
        )

    for resource in wrong_type_resources:
        color_print(
            f'{package}: Resource {resource.name} has wrong type',
            color=Color.YELLOW,
        )

    xmls, missing_xmls = read_overlay_xmls(
        overlay_path,
        overlay_xmls,
        package_xmls,
    )

    for xml in missing_xmls:
        color_print(
            f'{package}: XML {xml} not found in {target_package}',
            color=Color.RED,
        )

    def attrib_needs_aapt_raw(_attrib_key: str, attrib_value: str):
        return attrib_value.startswith('0') and len(attrib_value) > 1

    aapt_raw = False
    for xml_name, xml_data in xmls.items():
        aapt_raw = xml_attrib_matches(xml_data, attrib_needs_aapt_raw)
        if not aapt_raw:
            continue

        color_print(
            f'{package}: XML {xml_name} needs raw aapt flag',
            color=Color.YELLOW,
        )
        break

    if not grouped_resources and not xmls:
        raise ValueError(f'{package}: No resources left in overlay')

    remove_overlay_resources(overlay_path)
    write_grouped_resources(grouped_resources, output_path)
    write_overlay_xmls(xmls, output_path)

    rro_manifest_path = path.join(output_path, ANDROID_MANIFEST_NAME)
    write_manifest(rro_manifest_path, package, target_package, overlay_attrs)

    return package, aapt_raw

# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import subprocess
from os import path

from bp.bp_utils import get_partition_specific
from rro.manifest import (
    ANDROID_MANIFEST_NAME,
    parse_overlay_manifest,
    write_manifest,
)
from rro.resources import (
    RESOURCES_DIR,
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
'''.lstrip()
        )


def _remove_overlay_package(overlay_path: str, output_path: str, package: str, msg: str):
    color_print(f'{package}: {msg}, removing overlay package', color=Color.YELLOW)

    for p in (output_path, overlay_path):
        if not p or not path.isdir(p):
            continue
        subprocess.run(['rm', '-rf', '--', p], check=False)
        if overlay_path == output_path:
            break


def process_rro(
    overlay_path: str,
    output_path: str,
    android_manifest_name: str = ANDROID_MANIFEST_NAME,
    resources_dir: str = RESOURCES_DIR,
    maintain_copyrights: bool = False,
):
    manifest_path = path.join(overlay_path, android_manifest_name)

    package, target_package, overlay_attrs = parse_overlay_manifest(
        manifest_path,
    )

    overlay_resources, overlay_xmls = parse_overlay_resources(
        overlay_path, resources_dir
    )
    if not overlay_resources and not overlay_xmls:
        _remove_overlay_package(overlay_path, output_path, package, 'No resources in overlay')
        return False

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

    for resource_name in sorted(missing_resources):
        color_print(
            f'{package}: Resource {resource_name} not found in {target_package}',
            color=Color.RED,
        )

    for resource_name in sorted(identical_resources):
        color_print(
            f'{package}: Resource {resource_name} identical in {target_package}',
            color=Color.YELLOW,
        )

    for resource_name, wrong_type, correct_type in sorted(wrong_type_resources):
        color_print(
            f'{package}: Resource {resource_name} has wrong type {wrong_type}, '
            f'expected {correct_type}',
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
        _remove_overlay_package(overlay_path, output_path, package, 'No resources left in overlay')
        return False

    # Preserve existing res/values/*.xml headers BEFORE we delete res/
    preserved_prefixes = None
    if maintain_copyrights:
        preserved_prefixes = {}
        for rel_xml_path in grouped_resources.keys():
            existing_xml_path = path.join(output_path, rel_xml_path)
            preserved = None
            try:
                with open(existing_xml_path, 'rb') as f:
                    data = f.read()
                idx = data.find(b'<resources')
                if idx != -1:
                    preserved = data[:idx]
            except Exception:
                preserved = None
            preserved_prefixes[existing_xml_path] = preserved

    remove_overlay_resources(overlay_path)
    write_grouped_resources(
        grouped_resources,
        output_path,
        maintain_copyrights=maintain_copyrights,
        preserved_prefixes=preserved_prefixes,
    )
    write_overlay_xmls(xmls, output_path)

    rro_manifest_path = path.join(output_path, android_manifest_name)
    write_manifest(
        rro_manifest_path,
        package,
        target_package,
        overlay_attrs,
        maintain_copyrights=maintain_copyrights,
    )

    return aapt_raw

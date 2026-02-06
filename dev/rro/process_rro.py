# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import re
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
    read_raw_resources,
    remove_overlay_resources,
    write_grouped_resources,
    write_overlay_raw_resources,
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
    package = simplify_rro_package(package)

    overlay_resources, overlay_raw_resources = parse_overlay_resources(
        overlay_path, resources_dir
    )
    if not overlay_resources and not overlay_raw_resources:
        raise ValueError(f'{package}: No resources in overlay')

    target_packages, target_package = get_target_packages(target_package)
    package_resources, package_raw_resources = find_target_package_resources(
        target_packages,
        overlay_resources,
        overlay_raw_resources,
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

    raw_resources, missing_raw_resources = read_raw_resources(
        overlay_path,
        overlay_raw_resources,
        package_raw_resources,
    )

    for raw_resource in missing_raw_resources:
        color_print(
            f'{package}: Raw resource {raw_resource} not found in {target_package}',
            color=Color.RED,
        )

    def attrib_needs_aapt_raw(_attrib_key: str, attrib_value: str):
        return attrib_value.startswith('0') and len(attrib_value) > 1

    aapt_raw = False
    for raw_resource_name, raw_resource_data in raw_resources.items():
        if not raw_resource_name.endswith('.xml'):
            continue

        aapt_raw = xml_attrib_matches(raw_resource_data, attrib_needs_aapt_raw)
        if not aapt_raw:
            continue

        color_print(
            f'{package}: Raw resource {raw_resource_name} needs raw aapt flag',
            color=Color.YELLOW,
        )
        break

    if not grouped_resources and not raw_resources:
        raise ValueError(f'{package}: No resources left in overlay')

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
    write_overlay_raw_resources(raw_resources, output_path)

    rro_manifest_path = path.join(output_path, android_manifest_name)
    write_manifest(
        rro_manifest_path,
        package,
        target_package,
        overlay_attrs,
        maintain_copyrights=maintain_copyrights,
    )

    return aapt_raw


RRO_NAME_SIMPLIFY_REGEX = re.compile(
    r'__[^_]+__auto_generated_rro_(vendor|product)$'
)
RRO_PACKAGE_SIMPLIFY_REGEX = re.compile(
    r'\.auto_generated_rro_(vendor|product)__$'
)


def simplify_rro_name(rro_name: str):
    # TODO: use dashes if package has dashes?
    return RRO_NAME_SIMPLIFY_REGEX.sub(
        lambda m: f'Overlay{m.group(1).capitalize()}',
        rro_name,
    )


def simplify_rro_package(rro_package: str):
    return RRO_PACKAGE_SIMPLIFY_REGEX.sub(
        r'.overlay.\1',
        rro_package,
    )

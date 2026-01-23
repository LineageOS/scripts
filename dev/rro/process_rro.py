# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from os import path
from typing import Optional

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


def _read_existing_android_bp_header(android_bp_path: str) -> Optional[str]:
    """
    Preserve the leading header block of an existing Android.bp file.

    We treat consecutive leading comment lines ("// ...") and blank lines
    as the header. Returns the header string (including trailing newlines)
    or None if not found.
    """
    if not path.exists(android_bp_path):
        return None

    try:
        with open(android_bp_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception:
        return None

    header_lines = []
    started_body = False

    for line in lines:
        stripped = line.lstrip()
        if not started_body:
            if stripped.startswith('//') or stripped == '' or stripped == '\n':
                header_lines.append(line)
                continue
            started_body = True
            break

    if not header_lines:
        return None

    return ''.join(header_lines)


def write_rro_android_bp(
    apk_path: str,
    android_bp_path: str,
    package: str,
    aapt_raw: bool,
    maintain_copyrights: bool = False,
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

    with open(android_bp_path, 'w', encoding='utf-8') as o:
        if maintain_copyrights:
            existing_header = _read_existing_android_bp_header(android_bp_path)
            if existing_header is not None:
                o.write(existing_header.rstrip('\n'))
                o.write('\n\n')
            else:
                o.write(
                    '''
//
// SPDX-FileCopyrightText: The LineageOS Project
// SPDX-License-Identifier: Apache-2.0
//

'''.lstrip()
                )
        else:
            o.write(
                '''
//
// SPDX-FileCopyrightText: The LineageOS Project
// SPDX-License-Identifier: Apache-2.0
//

'''.lstrip()
            )

        o.write(
            f'''
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

    overlay_resources, overlay_xmls = parse_overlay_resources(
        overlay_path, resources_dir
    )
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

    for missing in missing_xmls:
        color_print(
            f'{package}: XML {missing} not found in {target_package}',
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

    # Capture existing headers BEFORE removing res/ (remove_overlay_resources)
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

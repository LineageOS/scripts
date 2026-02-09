# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import re
from os import path
from tempfile import TemporaryDirectory
from typing import Dict, List, Optional, Set

from bp.bp_utils import get_partition_specific
from rro.manifest import (
    ANDROID_MANIFEST_NAME,
    parse_overlay_manifest,
    write_manifest,
)
from rro.resources import (
    RESOURCES_DIR,
    TRANSLATABLE_KEY,
    find_target_package_resources,
    fixup_incorrect_resources_type,
    group_overlay_resources_rel_path,
    parse_overlay_resources,
    read_raw_resources,
    remove_overlay_resources,
    resources_dict,
    write_grouped_resources,
    write_overlay_raw_resources,
)
from rro.target_package import get_target_packages
from utils.utils import Color, color_print
from utils.xml_utils import xml_attrib_matches, xml_element_canonical_str


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


def is_rro_equal(overlay_path: str, aosp_overlay_path: str):
    overlay_resources, overlay_raw_resources = parse_overlay_resources(
        overlay_path,
        RESOURCES_DIR,
    )

    aosp_overlay_resources, aosp_overlay_raw_resources = (
        parse_overlay_resources(
            aosp_overlay_path,
            RESOURCES_DIR,
        )
    )

    if overlay_resources.keys() != aosp_overlay_resources.keys():
        return False

    if overlay_raw_resources.keys() != aosp_overlay_raw_resources.keys():
        return False

    for k in overlay_resources.keys():
        first_element = overlay_resources[k].element
        second_element = aosp_overlay_resources[k].element

        # Overlays don't have translatable=false, remove it to fix
        # equality check
        if TRANSLATABLE_KEY in first_element.attrib:
            del first_element.attrib[TRANSLATABLE_KEY]

        if TRANSLATABLE_KEY in second_element.attrib:
            del second_element.attrib[TRANSLATABLE_KEY]

        first_resource = xml_element_canonical_str(
            overlay_resources[k].element,
        )

        second_resource = xml_element_canonical_str(
            aosp_overlay_resources[k].element,
        )

        if first_resource != second_resource:
            return False

    for k in overlay_raw_resources.keys():
        if overlay_raw_resources[k] != aosp_overlay_raw_resources[k]:
            return False

    return True


def is_rro_equal_with_aosp(overlay_path: str, aosp_overlay_path: str):
    with TemporaryDirectory() as tmp_dir:
        process_rro(aosp_overlay_path, tmp_dir)

        return is_rro_equal(overlay_path, tmp_dir)


def process_rro(
    overlay_path: str,
    output_path: str,
    android_manifest_name: str = ANDROID_MANIFEST_NAME,
    resources_dir: str = RESOURCES_DIR,
    all_packages_resources_map: Optional[Dict[str, resources_dict]] = None,
    remove_identical: bool = False,
    maintain_copyrights: bool = False,
    remove_resources: Optional[Set[str]] = None,
    keep_packages: Optional[Set[str]] = None,
):
    if all_packages_resources_map is None:
        all_packages_resources_map = {}
    if remove_resources is None:
        remove_resources = set()
    if keep_packages is None:
        keep_packages = set()

    manifest_path = path.join(overlay_path, android_manifest_name)

    package, target_package, overlay_attrs = parse_overlay_manifest(
        manifest_path,
    )
    is_kept_target_package = target_package in keep_packages
    package = simplify_rro_package(package)

    overlay_resources, overlay_raw_resources = parse_overlay_resources(
        overlay_path,
        resources_dir,
        remove_resources,
    )
    if not overlay_resources and not overlay_raw_resources:
        raise ValueError(f'{package}: No resources in overlay')

    package_resources = {}
    package_raw_resources = {}
    if not is_kept_target_package:
        target_packages, target_package = get_target_packages(target_package)
        package_resources, package_raw_resources = (
            find_target_package_resources(
                target_packages,
                overlay_resources,
                overlay_raw_resources,
            )
        )

    wrong_type_resources = fixup_incorrect_resources_type(
        overlay_resources,
        package_resources,
    )

    package_resources_map = all_packages_resources_map.setdefault(
        target_package,
        {},
    )

    (
        grouped_resources,
        missing_resources,
        identical_resources,
        shadowed_resources,
    ) = group_overlay_resources_rel_path(
        overlay_resources,
        package_resources,
        manifest_path,
        package_resources_map,
        remove_identical,
        is_kept_target_package,
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

    for resource_name in sorted(shadowed_resources):
        color_print(
            f'{package}: Resource {resource_name} shadowed in {target_package}',
            color=Color.YELLOW,
        )

    for resource_name, wrong_type, correct_type in sorted(wrong_type_resources):
        color_print(
            f'{package}: Resource {resource_name} has wrong type {wrong_type}, '
            f'expected {correct_type}, corrected automatically',
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

    def attrib_needs_aapt_raw(
        _attrib_key: str | bytes,
        attrib_value: str | bytes,
    ):
        if not len(attrib_value) > 1:
            return False

        if isinstance(attrib_value, bytes):
            return attrib_value.startswith(b'0')
        elif isinstance(attrib_value, str):
            return attrib_value.startswith('0')
        else:
            assert False

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
    preserved_prefixes: Dict[str, bytes] = {}
    if maintain_copyrights:
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
                pass

            if preserved is None:
                continue

            preserved_prefixes[existing_xml_path] = preserved

    remove_overlay_resources(output_path)
    write_grouped_resources(
        grouped_resources,
        output_path,
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

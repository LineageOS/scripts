# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import re
import shutil
from os import path
from typing import Dict, Optional, Set, Tuple

from bp.bp_utils import ANDROID_BP_NAME, get_partition_specific
from rro.manifest import (
    ANDROID_MANIFEST_NAME,
    parse_overlay_manifest,
    write_manifest,
)
from rro.resources import (
    RESOURCES_DIR,
    RawResource,
    XMLResource,
    find_target_package_resources,
    overlay_resource_fixup_from_package,
    overlay_resource_remove_identical,
    overlay_resource_remove_shadowed,
    overlay_resource_split_by_type,
    overlay_resources_fixup_tag,
    overlay_resources_group_by_rel_path,
    overlay_resources_remove,
    overlay_resources_remove_missing,
    parse_overlay_resources,
    raw_resources_need_aapt_raw,
    read_xml_resources_prefix,
    resources_reference_name_sorted,
    write_grouped_resources,
    write_overlay_raw_resources,
)
from rro.target_package import (
    find_overlay_android_bp_path_by_name,
    get_target_packages,
)
from utils.utils import Color, color_print


def write_rro_android_bp(
    android_bp_path: str,
    package: str,
    aapt_raw: bool,
    partition: Optional[str] = None,
):
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
    overlay_resources = parse_overlay_resources(
        overlay_path,
        RESOURCES_DIR,
    )

    aosp_overlay_resources = parse_overlay_resources(
        aosp_overlay_path,
        RESOURCES_DIR,
    )

    return overlay_resources == aosp_overlay_resources


def check_rro_matches_aosp(
    rro_name: str,
    package: str,
    target_package: str,
    resources: Set[XMLResource],
    raw_resources: Set[RawResource],
):
    aosp_rro_android_bp_path = find_overlay_android_bp_path_by_name(
        rro_name,
    )
    if aosp_rro_android_bp_path is None:
        return

    (
        aosp_package,
        aosp_target_package,
        _,
        aosp_resources,
        aosp_raw_resources,
        _,
        _,
    ) = parse_rro(
        aosp_rro_android_bp_path,
        rro_name,
    )

    if package != aosp_package or target_package != aosp_target_package:
        return

    if resources == aosp_resources and raw_resources == aosp_raw_resources:
        raise ValueError(f'Overlay {rro_name} identical to AOSP')

    color_print(
        f'Overlay {rro_name} already exists in AOSP but is not '
        f'identical at {aosp_rro_android_bp_path}',
        color=Color.YELLOW,
    )

    print('Resources in RRO:')
    for resource in resources - aosp_resources:
        print(resource)
    print()

    print('Resources in AOSP:')
    for resource in aosp_resources - resources:
        print(resource)
    print()


def parse_rro(
    overlay_path: str,
    rro_name: str,
    manifest_name: str = ANDROID_MANIFEST_NAME,
    resources_dir: str = RESOURCES_DIR,
    all_packages_resources_map: Optional[
        Dict[
            str,
            Dict[Tuple[str, ...], Tuple[str, str]],
        ]
    ] = None,
    remove_shadowed_resources: bool = False,
    remove_missing_resources: bool = False,
    check_matches_aosp: bool = False,
    remove_resources: Optional[Set[Tuple[str | None, str]]] = None,
    keep_packages: Optional[Set[str]] = None,
    exclude_overlays: Optional[Set[str]] = None,
    exclude_packages: Optional[Set[str]] = None,
):
    if all_packages_resources_map is None:
        all_packages_resources_map = {}
    if remove_resources is None:
        remove_resources = set()
    if keep_packages is None:
        keep_packages = set()
    if exclude_overlays is None:
        exclude_overlays = set()
    if exclude_packages is None:
        exclude_packages = set()

    manifest_path = path.join(overlay_path, manifest_name)

    package, target_package, overlay_attrs = parse_overlay_manifest(
        manifest_path,
    )
    if target_package in exclude_packages:
        raise ValueError(f'{package}: Excluded by {target_package}')

    if package in exclude_overlays:
        raise ValueError(f'{package}: Excluded')
    package = simplify_rro_package(package)
    if package in exclude_overlays:
        raise ValueError(f'{package}: Excluded')

    overlay_resources = parse_overlay_resources(
        overlay_path,
        resources_dir,
    )
    if not overlay_resources:
        raise ValueError(f'{package}: No resources in overlay')

    target_packages, target_package = get_target_packages(target_package)
    if target_package in exclude_packages:
        raise ValueError(f'{package}: Excluded by {target_package}')

    package_resources, module_name = find_target_package_resources(
        target_packages,
        overlay_resources,
    )

    if len(target_packages) > 1:
        color_print(
            f'{package}: found multiple matches for {target_package}:',
            color=Color.YELLOW,
        )
        print(', '.join(t[1] for t in target_packages))
        color_print(
            f'{package}: picked {module_name}',
            color=Color.GREEN,
        )

    if remove_missing_resources and package_resources is None:
        raise ValueError(f'Unknown package name: {target_package}')

    removed_resources = overlay_resources_remove(
        overlay_resources,
        remove_resources,
        target_package,
    )
    for resource in resources_reference_name_sorted(removed_resources):
        color_print(
            f'{package}: {resource} removed in {target_package}',
            color=Color.YELLOW,
        )

    if package_resources is not None:
        wrong_tag_resources = overlay_resources_fixup_tag(
            overlay_resources,
            package_resources,
        )
        for resource, wrong_type, correct_type in sorted(wrong_tag_resources):
            color_print(
                f'{package}: {resource} has wrong type {wrong_type}, '
                f'expected {correct_type}, corrected automatically',
                color=Color.YELLOW,
            )

    if package_resources is not None and remove_missing_resources:
        missing_resources = overlay_resources_remove_missing(
            overlay_resources,
            package_resources,
            manifest_path,
        )
        for resource in resources_reference_name_sorted(missing_resources):
            color_print(
                f'{package}: {resource} not found in {target_package}',
                color=Color.RED,
            )

    if remove_shadowed_resources:
        package_resources_map = all_packages_resources_map.setdefault(
            target_package,
            {},
        )
        shadowed_resources = overlay_resource_remove_shadowed(
            overlay_resources,
            package_resources_map,
            package,
            rro_name,
        )
        for resource, shadower_rro_name, shadower_package in sorted(
            set(shadowed_resources)
        ):
            color_print(
                f'{package}: {resource} shadowed in {shadower_rro_name} ({shadower_package})',
                color=Color.YELLOW,
            )

    if package_resources is not None and remove_shadowed_resources:
        identical_resources = overlay_resource_remove_identical(
            overlay_resources,
            package_resources,
        )

        for resource in resources_reference_name_sorted(identical_resources):
            color_print(
                f'{package}: {resource} identical in {target_package}',
                color=Color.YELLOW,
            )

    if not overlay_resources:
        raise ValueError(f'{package}: No resources left in overlay')

    if package_resources is not None:
        overlay_resource_fixup_from_package(
            overlay_resources,
            package_resources,
        )

    resources, raw_resources = overlay_resource_split_by_type(
        overlay_resources,
    )

    if check_matches_aosp:
        check_rro_matches_aosp(
            rro_name,
            package,
            target_package,
            resources,
            raw_resources,
        )

    grouped_resources = overlay_resources_group_by_rel_path(resources)

    overlay_raw_resource_needs_aapt_flag = raw_resources_need_aapt_raw(
        raw_resources,
    )
    aapt_raw = overlay_raw_resource_needs_aapt_flag is not None
    if overlay_raw_resource_needs_aapt_flag is not None:
        rel_path = overlay_raw_resource_needs_aapt_flag.rel_path
        color_print(
            f'{package}: Raw resource {rel_path} needs raw aapt flag',
            color=Color.YELLOW,
        )

    return (
        package,
        target_package,
        overlay_attrs,
        resources,
        raw_resources,
        grouped_resources,
        aapt_raw,
    )


def process_rro(
    input_path: str,
    output_path: str,
    rro_name: str,
    manifest_name: str = ANDROID_MANIFEST_NAME,
    resources_dir: str = RESOURCES_DIR,
    all_packages_resources_map: Optional[
        Dict[
            str,
            Dict[Tuple[str, ...], Tuple[str, str]],
        ]
    ] = None,
    maintain_copyrights: bool = False,
    remove_shadowed_resources: bool = False,
    remove_missing_resources: bool = False,
    check_matches_aosp: bool = False,
    remove_resources: Optional[Set[Tuple[str | None, str]]] = None,
    keep_packages: Optional[Set[str]] = None,
    exclude_overlays: Optional[Set[str]] = None,
    exclude_packages: Optional[Set[str]] = None,
    partition: Optional[str] = None,
):
    (
        package,
        target_package,
        overlay_attrs,
        _,
        raw_resources,
        grouped_resources,
        aapt_raw,
    ) = parse_rro(
        input_path,
        rro_name,
        manifest_name,
        resources_dir,
        all_packages_resources_map,
        remove_shadowed_resources=remove_shadowed_resources,
        remove_missing_resources=remove_missing_resources,
        check_matches_aosp=check_matches_aosp,
        remove_resources=remove_resources,
        keep_packages=keep_packages,
        exclude_overlays=exclude_overlays,
        exclude_packages=exclude_packages,
    )

    # Preserve existing res/values/*.xml headers BEFORE we delete res/
    preserved_prefixes: Dict[str, bytes] = {}
    if maintain_copyrights:
        preserved_prefixes = read_xml_resources_prefix(
            grouped_resources,
            output_path,
        )

    res_dir = path.join(output_path, resources_dir)
    shutil.rmtree(res_dir, ignore_errors=True)

    write_grouped_resources(
        grouped_resources,
        output_path,
        resources_dir,
        preserved_prefixes,
    )

    write_overlay_raw_resources(
        raw_resources,
        output_path,
        resources_dir,
    )

    rro_manifest_path = path.join(output_path, manifest_name)
    write_manifest(
        rro_manifest_path,
        package,
        target_package,
        overlay_attrs,
        maintain_copyrights=maintain_copyrights,
    )

    android_bp_path = path.join(output_path, ANDROID_BP_NAME)
    write_rro_android_bp(
        android_bp_path,
        rro_name,
        aapt_raw,
        partition,
    )


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

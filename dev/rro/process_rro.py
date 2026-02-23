# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import re
from os import path
from pathlib import Path
from typing import Dict, FrozenSet, NotRequired, Optional, Set, Tuple, TypedDict

from bp.bp_utils import ANDROID_BP_NAME, get_partition_specific
from rro.manifest import (
    ANDROID_MANIFEST_NAME,
    parse_overlay_manifest,
    write_manifest,
)
from rro.resources import (
    RESOURCES_DIR,
    Resource,
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
    resources: Set[Resource],
):
    aosp_rro_android_bp_path = find_overlay_android_bp_path_by_name(
        rro_name,
    )
    if aosp_rro_android_bp_path is None:
        return

    manifest_path = path.join(aosp_rro_android_bp_path, ANDROID_MANIFEST_NAME)
    aosp_package, aosp_target_package, _ = parse_overlay_manifest(
        manifest_path,
    )

    aosp_resources = parse_rro(
        aosp_rro_android_bp_path,
        package,
        target_package,
    )

    if package != aosp_package or target_package != aosp_target_package:
        return

    if resources == aosp_resources:
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
    package: str,
    target_package: str,
    manifest_name: str = ANDROID_MANIFEST_NAME,
    resources_dir: str = RESOURCES_DIR,
    package_resources_map: Optional[Dict[Tuple[str, ...], str]] = None,
    remove_shadowed_resources: bool = False,
    remove_missing_resources: bool = False,
    remove_resources: Optional[FrozenSet[str]] = None,
    keep_packages: Optional[Set[str]] = None,
    keep_resources: Optional[FrozenSet[str]] = None,
):
    if package_resources_map is None:
        package_resources_map = {}
    if remove_resources is None:
        remove_resources = frozenset()
    if keep_packages is None:
        keep_packages = set()
    if keep_resources is None:
        keep_resources = frozenset()

    manifest_path = path.join(overlay_path, manifest_name)

    overlay_resources = parse_overlay_resources(
        overlay_path,
        resources_dir,
    )
    if not overlay_resources:
        raise ValueError(f'{package}: No resources in overlay')

    target_packages = get_target_packages(target_package)

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

    if (
        remove_missing_resources
        and package_resources is None
        and target_package not in keep_packages
    ):
        raise ValueError(f'Unknown package name: {target_package}')

    removed_resources = overlay_resources_remove(
        overlay_resources,
        remove_resources,
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
        for old_resource, new_resource in sorted(wrong_tag_resources):
            color_print(
                f'{package}: {old_resource} -> {new_resource}',
                color=Color.YELLOW,
            )

    if package_resources is not None and remove_missing_resources:
        missing_resources, kept_resources = overlay_resources_remove_missing(
            overlay_resources,
            package_resources,
            manifest_path,
            keep_resources,
        )
        for resource in resources_reference_name_sorted(missing_resources):
            color_print(
                f'{package}: {resource} not found in {target_package}',
                color=Color.RED,
            )
        for resource in resources_reference_name_sorted(kept_resources):
            color_print(
                f'{package}: {resource} kept',
                color=Color.GREEN,
            )

    if remove_shadowed_resources:
        shadowed_resources = overlay_resource_remove_shadowed(
            overlay_resources,
            package_resources_map,
            package,
        )
        for resource, shadower_package in sorted(set(shadowed_resources)):
            color_print(
                f'{package}: {resource} shadowed in {shadower_package}',
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

    return overlay_resources


def write_rro(
    overlay_resources: Set[Resource],
    output_path: str,
    rro_name: str,
    package: str,
    target_package: str,
    overlay_attrs: Dict[str, str],
    preserved_prefixes: Optional[Dict[str, bytes]] = None,
    partition: Optional[str] = None,
):
    resources, raw_resources = overlay_resource_split_by_type(
        overlay_resources,
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

    write_grouped_resources(
        grouped_resources,
        output_path,
        RESOURCES_DIR,
        preserved_prefixes,
    )

    write_overlay_raw_resources(
        raw_resources,
        output_path,
        RESOURCES_DIR,
    )

    write_manifest(
        output_path,
        ANDROID_MANIFEST_NAME,
        package,
        target_package,
        overlay_attrs,
        preserved_prefixes=preserved_prefixes,
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
RRO_NAME_CHR_SIMPLIFY_REGEX = re.compile(
    r'__[^_]+__auto_generated_characteristics_rro$'
)
RRO_PACKAGE_SIMPLIFY_REGEX = re.compile(
    r'\.auto_generated_rro_(vendor|product)__$'
)
RRO_PACKAGE_CHR_SIMPLIFY_REGEX = re.compile(
    r'\.auto_generated_characteristics_rro'
)


def simplify_rro_name(
    rro_name: str,
    device: Optional[str],
    replaced_device: Optional[str] = None,
):
    if device is None:
        suffix = ''
    else:
        suffix = device.capitalize()

    original_rro_name = rro_name
    rro_name = rro_name.replace('framework-res', 'FrameworkRes')
    rro_name = RRO_NAME_SIMPLIFY_REGEX.sub(
        lambda m: f'Overlay{m.group(1).capitalize()}{suffix}',
        rro_name,
    )
    rro_name = RRO_NAME_CHR_SIMPLIFY_REGEX.sub(
        f'Overlay{suffix}',
        rro_name,
    )
    if replaced_device is not None and device is not None:
        rro_name = rro_name.replace(
            replaced_device.capitalize(),
            device.capitalize(),
        )

    return rro_name, original_rro_name


def simplify_rro_package(
    rro_package: str,
    device: Optional[str],
    replaced_device: Optional[str] = None,
):
    if device is None:
        suffix = ''
    else:
        suffix = f'.{device}'

    original_rro_package = rro_package
    rro_package = RRO_PACKAGE_SIMPLIFY_REGEX.sub(
        rf'.overlay.\1{suffix}',
        rro_package,
    )
    rro_package = RRO_PACKAGE_CHR_SIMPLIFY_REGEX.sub(
        rf'.overlay{suffix}',
        rro_package,
    )
    if replaced_device is not None and device is not None:
        rro_package = rro_package.replace(
            replaced_device,
            device,
        )

    return rro_package, original_rro_package


RRO_META_NAME = '.rro-meta.json'


class RROMeta(TypedDict):
    original_rro_name: str
    original_package: str
    original_target_package: str
    device: NotRequired[str]


def write_rro_meta(
    output_path: Path,
    rro_name: str,
    package: str,
    target_package: str,
    device: Optional[str],
):
    meta: RROMeta = {
        'original_rro_name': rro_name,
        'original_package': package,
        'original_target_package': target_package,
    }

    if device is not None:
        meta['device'] = device

    rro_meta_path = Path(output_path, RRO_META_NAME)
    with open(rro_meta_path, 'w') as o:
        json.dump(meta, o, indent=4, sort_keys=True)
        o.write('\n')


def read_rro_meta(overlay_path: Path) -> RROMeta:
    rro_meta_path = Path(overlay_path, RRO_META_NAME)
    with open(rro_meta_path, 'r') as i:
        return json.load(i)


def overlay_attrs_key(
    overlay_attrs: Dict[str, str],
    with_priority: bool = False,
):
    return tuple(
        sorted(
            (k, v)
            for k, v in overlay_attrs.items()
            if with_priority or k != 'priority'
        )
    )

# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from os import path
from pathlib import Path
from typing import (
    Dict,
    FrozenSet,
    List,
    NotRequired,
    Optional,
    Tuple,
    TypedDict,
)

from bp.bp_module import parse_bp_rro_module
from bp.bp_utils import (
    ANDROID_BP_NAME,
    get_partition_specific,
    partition_to_priority,
)
from rro.manifest import (
    ANDROID_MANIFEST_NAME,
    parse_overlay_manifest,
    write_manifest,
)
from rro.resources import (
    RESOURCES_DIR,
    Resource,
    ResourceMap,
    find_target_package_resources,
    is_resource_in_entries,
    overlay_resource_fixup_from_package,
    overlay_resources_fixup_tag,
    overlay_resources_remove,
    overlay_resources_remove_missing,
    parse_overlay_resources,
    raw_resources_need_aapt_raw,
    remove_identical_resource,
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


def get_rro_resources(package: str, resources_path: str):
    resources = parse_overlay_resources(resources_path)
    if not resources:
        raise ValueError(f'{package}: No resources in overlay')

    return resources


def get_rro_target_package_resources(
    package: str,
    target_package: str,
    resources: ResourceMap,
    allow_missing: bool,
):
    target_packages = get_target_packages(target_package)
    if not target_packages and not allow_missing:
        raise ValueError(f'{package}: Unknown package name {target_package}')

    package_resources, module_name = find_target_package_resources(
        target_packages,
        resources,
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

    return package_resources


def check_rro_matches_aosp(
    rro_name: str,
    package: str,
    target_package: str,
    resources: ResourceMap,
):
    aosp_rro_android_bp_dir = find_overlay_android_bp_path_by_name(
        rro_name,
    )
    if aosp_rro_android_bp_dir is None:
        return

    android_bp_path = Path(aosp_rro_android_bp_dir, ANDROID_BP_NAME)
    statement = parse_bp_rro_module(android_bp_path)

    manifest = statement.get('manifest', ANDROID_MANIFEST_NAME)
    manifest_path = Path(aosp_rro_android_bp_dir, manifest)

    resources_dir = statement.get('resource_dirs', [RESOURCES_DIR])[0]
    resources_path = Path(aosp_rro_android_bp_dir, resources_dir)

    aosp_package, aosp_target_package, _ = parse_overlay_manifest(
        str(manifest_path),
    )

    if package != aosp_package or target_package != aosp_target_package:
        return

    aosp_resources = parse_overlay_resources(str(resources_path))
    aosp_package_resources = get_rro_target_package_resources(
        package=aosp_package,
        target_package=aosp_target_package,
        resources=aosp_resources,
        allow_missing=True,
    )
    fixup_rro_resources(
        package=aosp_package,
        resources=aosp_resources,
        package_resources=aosp_package_resources,
    )

    if resources == aosp_resources:
        raise ValueError(f'Overlay {rro_name} identical to AOSP')

    color_print(
        f'Overlay {rro_name} already exists in AOSP but is not '
        f'identical at {aosp_rro_android_bp_dir}',
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


def fixup_rro_resources(
    package: str,
    resources: ResourceMap,
    package_resources: Optional[ResourceMap],
):
    if package_resources is None:
        return

    wrong_tag_resources = overlay_resources_fixup_tag(
        resources,
        package_resources,
    )
    for old_resource, new_resource in sorted(wrong_tag_resources):
        color_print(
            f'{package}: {old_resource} -> {new_resource}',
            color=Color.YELLOW,
        )

    overlay_resource_fixup_from_package(
        resources,
        package_resources,
    )


def remove_rro_resources(
    package: str,
    target_package: str,
    manifest_path: str,
    resources: ResourceMap,
    package_resources: Optional[ResourceMap],
    remove_resources: FrozenSet[str],
    keep_resources: FrozenSet[str],
):
    removed_resources = overlay_resources_remove(
        resources,
        remove_resources,
    )
    for resource in resources_reference_name_sorted(removed_resources):
        color_print(
            f'{package}: {resource} removed in {target_package}',
            color=Color.YELLOW,
        )

    if not resources:
        raise ValueError(f'{package}: No resources left in overlay')

    if package_resources is None:
        return

    missing_resources, kept_resources = overlay_resources_remove_missing(
        resources,
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

    if not resources:
        raise ValueError(f'{package}: No resources left in overlay')


def write_rro(
    overlay_resources: ResourceMap,
    output_path: str,
    rro_name: str,
    package: str,
    target_package: str,
    overlay_attrs: Dict[str, str],
    preserved_prefixes: Optional[Dict[str, bytes]] = None,
    partition: Optional[str] = None,
):
    overlay_raw_resource_needs_aapt_flag = raw_resources_need_aapt_raw(
        overlay_resources,
    )
    aapt_raw = overlay_raw_resource_needs_aapt_flag is not None
    if overlay_raw_resource_needs_aapt_flag is not None:
        rel_path = overlay_raw_resource_needs_aapt_flag.rel_path
        color_print(
            f'{package}: Raw resource {rel_path} needs raw aapt flag',
            color=Color.YELLOW,
        )

    write_grouped_resources(
        overlay_resources,
        output_path,
        RESOURCES_DIR,
        preserved_prefixes,
    )

    write_overlay_raw_resources(
        overlay_resources,
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


@dataclass
class OverlayPriorityData:
    package: str
    target_package: str
    partition: str
    priority: int
    resources: ResourceMap
    package_resources: Optional[ResourceMap]
    prefer_resources: FrozenSet[str]
    attrs: Dict[str, str]
    immutable: bool


def resource_sort_key(ro: Tuple[Resource, OverlayPriorityData]):
    return (
        # Preferred resources first
        is_resource_in_entries(ro[1].prefer_resources, ro[0]),
        # Partition priority
        partition_to_priority(ro[1].partition),
        # Overlay priority
        ro[1].priority,
    )


def remove_rros_shadowed_resources(
    overlays: List[OverlayPriorityData],
    remove_identical: bool,
):
    undetermined_resource_priorities: List[Tuple[str, List[str]]] = []
    resource_map: Dict[
        # resource keys
        Tuple[
            # target package
            str,
            # overlay attrs
            Tuple[Tuple[str, str], ...],
            # resource keys
            Tuple[str, ...],
        ],
        List[
            Tuple[
                Resource,
                OverlayPriorityData,
            ],
        ],
    ] = {}

    for overlay in overlays:
        for resource in overlay.resources:
            resource_map.setdefault(
                (
                    overlay.target_package,
                    overlay_attrs_key(overlay.attrs),
                    resource.keys,
                ),
                [],
            ).append(
                (
                    resource,
                    overlay,
                )
            )

    for resources in resource_map.values():
        resources.sort(key=resource_sort_key, reverse=True)

        preferred_resource_overlay = resources[0]
        preferred_resource = resources[0][0]
        preferred_overlay = resources[0][1]
        preferred_resource_sort_key = resource_sort_key(
            preferred_resource_overlay,
        )

        preferred_packages: List[str] = []
        for ro in resources:
            if resource_sort_key(ro) != preferred_resource_sort_key:
                break

            preferred_packages.append(ro[1].package)
        preferred_packages.sort()

        if len(preferred_packages) > 1:
            undetermined_resource_priorities.append(
                (
                    preferred_resource.reference_name,
                    preferred_packages,
                )
            )

        # If we shadowed an immutable resource, do not check if the
        # preferred resource is identical to AOSP, as we cannot remove
        # it because the immutable shadowed resource would take priority
        shadowed_immutable = False
        shadowed_resources = resources[1:]
        for resource, overlay in shadowed_resources:
            if overlay.immutable:
                shadowed_immutable = True
                continue

            overlay.resources.remove(resource)

        if shadowed_immutable or not remove_identical:
            continue

        remove_identical_resource(
            preferred_resource,
            preferred_overlay.resources,
            preferred_overlay.package_resources,
        )

    return undetermined_resource_priorities

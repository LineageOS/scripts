# SPDX-FileCopyrightText: 2026 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import (
    Dict,
    FrozenSet,
    List,
    NotRequired,
    Optional,
    Set,
    Tuple,
    TypedDict,
)

from bp.bp_module import parse_bp_rro_module
from bp.bp_utils import (
    ANDROID_BP_NAME,
    get_module_partition,
    partition_to_priority,
    write_android_bp,
)
from rro.manifest import (
    ANDROID_MANIFEST_NAME,
    parse_overlay_manifest,
    write_manifest,
)
from rro.resource import Resource
from rro.resource_map import IndexFlags, PackageDirNamesIndex, ResourceMap
from rro.resources import (
    RESOURCES_DIR,
    find_target_package_resources,
    is_resource_in_entries,
    keep_referenced_resources_from_removal,
    overlay_resource_fixup_from_package,
    overlay_resources_remove,
    overlay_resources_remove_missing,
    parse_resources,
    read_xml_resources_prefix,
    resources_reference_name_sorted,
    write_resources,
)
from rro.target_package import (
    PackageMap,
    find_overlay_android_bp_path_by_name,
    fixup_target_package,
    get_target_packages,
)
from utils.utils import Color, color_print


def _str_frozenset() -> FrozenSet[str]:
    return frozenset()


def resource_set() -> Set[Resource]:
    return set()


@dataclass
class Overlay:
    name: str
    path: Path
    manifest_name: str
    resources_dir: str

    partition: str
    package: str
    target_package: str
    attrs: Dict[str, str]

    resources: ResourceMap

    immutable: bool = False
    package_resources: Optional[ResourceMap] = None
    prefer_resources: FrozenSet[str] = field(default_factory=_str_frozenset)

    preserved_prefixes: Optional[Dict[str, bytes]] = None
    removed_resources: Set[Resource] = field(default_factory=resource_set)

    device: Optional[str] = None
    original_name: Optional[str] = None
    original_package: Optional[str] = None
    original_target_package: Optional[str] = None

    @property
    def priority(self):
        return int(self.attrs.get('priority', 0))

    def attrs_key(self, with_priority: bool = False):
        return tuple(
            sorted(
                (k, v)
                for k, v in self.attrs.items()
                if with_priority or k != 'priority'
            )
        )


def filter_resource_entries(
    resource_entries: Set[Tuple[None | str, str]],
    target_package: str,
):
    return frozenset(
        resource_name
        for package, resource_name in resource_entries
        if package is None or package == target_package
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


def simplify_overlay_name(
    name: str,
    device: Optional[str],
    replaced_device: Optional[str] = None,
):
    if device is None:
        suffix = ''
    else:
        suffix = device.capitalize()

    original_name = name
    name = name.replace('framework-res', 'FrameworkRes')
    name = RRO_NAME_SIMPLIFY_REGEX.sub(
        lambda m: f'Overlay{m.group(1).capitalize()}{suffix}',
        name,
    )
    name = RRO_NAME_CHR_SIMPLIFY_REGEX.sub(
        f'Overlay{suffix}',
        name,
    )
    if replaced_device is not None and device is not None:
        name = name.replace(
            replaced_device.capitalize(),
            device.capitalize(),
        )

    return name, original_name


def simplify_overlay_package(
    package: str,
    device: Optional[str],
    replaced_device: Optional[str] = None,
):
    if device is None:
        suffix = ''
    else:
        suffix = f'.{device}'

    original_package = package
    package = RRO_PACKAGE_SIMPLIFY_REGEX.sub(
        rf'.overlay.\1{suffix}',
        package,
    )
    package = RRO_PACKAGE_CHR_SIMPLIFY_REGEX.sub(
        rf'.overlay{suffix}',
        package,
    )
    if replaced_device is not None and device is not None:
        package = package.replace(
            replaced_device,
            device,
        )

    return package, original_package


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


def parse_overlay_from_android_bp(
    overlay_path: Path,
    immutable: bool = False,
    track_index: bool = False,
    maintain_copyrights: bool = False,
    read_meta: bool = False,
    ignore_packages: Optional[Set[str]] = None,
    package_dir_names: Optional[PackageDirNamesIndex] = None,
    prefer_resources: Optional[Set[Tuple[Optional[str], str]]] = None,
    exclude_overlays: Optional[Set[str]] = None,
    exclude_packages: Optional[Set[str]] = None,
    original_name: Optional[str] = None,
    original_package: Optional[str] = None,
    original_target_package: Optional[str] = None,
    device: Optional[str] = None,
):
    if ignore_packages is None:
        ignore_packages = set()

    if prefer_resources is None:
        prefer_resources = set()

    if exclude_overlays is None:
        exclude_overlays = set()

    if exclude_packages is None:
        exclude_packages = set()

    android_bp_path = Path(overlay_path, ANDROID_BP_NAME)
    statement = parse_bp_rro_module(android_bp_path)

    name = statement['name']
    dir_name = overlay_path.name

    if name in ignore_packages or dir_name in ignore_packages:
        return None

    manifest = statement.get('manifest', ANDROID_MANIFEST_NAME)
    manifest_path = Path(overlay_path, manifest)

    resources_dir = statement.get('resource_dirs', [RESOURCES_DIR])[0]
    resources_path = Path(overlay_path, resources_dir)

    package, target_package, overlay_attrs = parse_overlay_manifest(
        str(manifest_path),
    )

    if read_meta:
        rro_meta = read_rro_meta(overlay_path)
        original_name = rro_meta['original_rro_name']
        package = rro_meta['original_package']
        target_package = rro_meta['original_target_package']
        device = rro_meta.get('device')

    package, original_package = simplify_overlay_package(
        package,
        device,
    )
    target_package, original_target_package = fixup_target_package(
        target_package,
    )

    if package in exclude_overlays:
        raise ValueError(f'{package}: Excluded')
    if original_package in exclude_overlays:
        raise ValueError(f'{original_package}: Excluded')

    if target_package in exclude_packages:
        raise ValueError(f'{package}: Excluded by {target_package}')
    if original_target_package in exclude_packages:
        raise ValueError(f'{package}: Excluded by {original_target_package}')

    module_partition = get_module_partition(statement)

    dir_names = (
        package_dir_names.for_package(target_package)
        if package_dir_names is not None
        else None
    )

    resources = ResourceMap(
        indices=IndexFlags.BY_REL_PATH
        | IndexFlags.BY_REFERENCE_NAME
        | IndexFlags.REFERENCES,
        # Dir names index to add to
        dir_names=dir_names,
    )

    parse_resources(
        resource_map=resources,
        resources_paths=[str(resources_path)],
        parse_all_values=True,
        read_raw_resources=True,
        track_index=track_index,
        # Dir names to parse, we are parsing an overlay here so we do not want
        # to limit these
        dir_names=None,
    )

    if not resources:
        shutil.rmtree(overlay_path, ignore_errors=True)
        color_print(f'{package}: No resources in overlay', color=Color.RED)
        return None

    preserved_prefixes = None
    if maintain_copyrights:
        preserved_prefixes = read_xml_resources_prefix(
            resources,
            str(overlay_path),
            extra_paths=[manifest],
        )

    return Overlay(
        name=name,
        path=overlay_path,
        manifest_name=manifest,
        resources_dir=resources_dir,
        partition=module_partition,
        package=package,
        target_package=target_package,
        attrs=overlay_attrs,
        immutable=immutable,
        resources=resources,
        prefer_resources=filter_resource_entries(
            prefer_resources,
            target_package,
        ),
        device=device,
        original_name=original_name,
        original_package=original_package,
        original_target_package=original_target_package,
        preserved_prefixes=preserved_prefixes,
    )


def parse_overlay_target_package_resources(
    package_map: PackageMap,
    overlay: Overlay,
):
    target_packages = get_target_packages(package_map, overlay.target_package)
    if not target_packages:
        return None

    package_resources, module_name = find_target_package_resources(
        target_packages=target_packages,
        resources=overlay.resources,
        parse_all_values=True,
        dir_names=overlay.resources.dir_names_to_names(),
    )

    overlay.package_resources = package_resources

    if len(target_packages) > 1:
        color_print(
            f'{overlay.package}: found multiple matches for {overlay.target_package}:',
            color=Color.YELLOW,
        )
        print(', '.join(t[1] for t in target_packages))
        color_print(
            f'{overlay.package}: picked {module_name}',
            color=Color.GREEN,
        )


def fixup_overlay_resources(overlay: Overlay):
    if overlay.package_resources is None:
        return

    wrong_tag_resources = overlay_resource_fixup_from_package(
        overlay.resources,
        overlay.package_resources,
    )
    for old_resource, new_resource in sorted(wrong_tag_resources):
        color_print(
            f'{overlay.package}: {old_resource} -> {new_resource}',
            color=Color.YELLOW,
        )


def write_overlay(
    overlay: Overlay,
    write_meta: bool = False,
):
    overlay.path.mkdir(parents=True, exist_ok=True)

    aapt_raw_resource = write_resources(
        overlay.resources,
        str(overlay.path),
        RESOURCES_DIR,
        overlay.preserved_prefixes,
    )

    write_manifest(
        str(overlay.path),
        ANDROID_MANIFEST_NAME,
        overlay.package,
        overlay.target_package,
        overlay.attrs,
        preserved_prefixes=overlay.preserved_prefixes,
    )

    aapt_raw = False
    if aapt_raw_resource is not None:
        aapt_raw = True
        rel_path = aapt_raw_resource.rel_path
        color_print(
            f'{overlay.package}: Raw resource {rel_path} needs raw aapt flag',
            color=Color.YELLOW,
        )

    android_bp_path = Path(overlay.path, ANDROID_BP_NAME)
    write_android_bp(
        android_bp_path,
        overlay.name,
        aapt_raw,
        overlay.partition,
    )

    if write_meta:
        assert overlay.original_name is not None
        assert overlay.original_package is not None
        assert overlay.original_target_package is not None
        write_rro_meta(
            overlay.path,
            overlay.original_name,
            overlay.original_package,
            overlay.original_target_package,
            overlay.device,
        )


def is_overlay_aosp(package_map: PackageMap, overlay: Overlay):
    aosp_rro_android_bp_dir = find_overlay_android_bp_path_by_name(
        package_map,
        overlay.name,
    )
    if aosp_rro_android_bp_dir is None:
        return

    aosp_overlay = parse_overlay_from_android_bp(
        Path(aosp_rro_android_bp_dir),
    )
    if aosp_overlay is None:
        return False

    if (
        overlay.package != aosp_overlay.package
        or overlay.target_package != aosp_overlay.target_package
    ):
        return False

    # Although only relevant package resources are parsed, we are checking for
    # equality, which means that we do not care about resources in this AOSP
    # overlay which are not in our overlay, so we can reuse the already parsed
    # package resources
    aosp_overlay.package_resources = overlay.package_resources

    fixup_overlay_resources(aosp_overlay)

    if overlay.resources == aosp_overlay.resources:
        return True

    color_print(
        f'Overlay {overlay.name} already exists in AOSP but is not '
        f'identical at {aosp_rro_android_bp_dir}',
        color=Color.YELLOW,
    )

    print('Resources in RRO:')
    for resource in overlay.resources:
        if resource not in aosp_overlay.resources:
            print(resource)
    print()

    print('Resources in AOSP:')
    for resource in aosp_overlay.resources:
        if resource not in overlay.resources:
            print(resource)
    print()

    return (False,)


def remove_overlay_resources(
    overlay: Overlay,
    remove_resources: FrozenSet[str],
):
    overlay_resources_remove(
        overlay.resources,
        remove_resources,
    )


def remove_missing_overlay_resources(
    overlay: Overlay,
    keep_resources: FrozenSet[str],
):
    if not overlay.resources:
        return

    if overlay.package_resources is None:
        return

    manifest_path = Path(overlay.path, overlay.manifest_name)
    missing_resources, kept_resources = overlay_resources_remove_missing(
        overlay.resources,
        overlay.package_resources,
        str(manifest_path),
        keep_resources,
    )

    for resource in resources_reference_name_sorted(missing_resources):
        color_print(
            f'{overlay.package}: {resource} not found in {overlay.target_package}',
            color=Color.RED,
        )
    for resource in resources_reference_name_sorted(kept_resources):
        color_print(
            f'{overlay.package}: {resource} kept',
            color=Color.GREEN,
        )


def resource_equality_key(ro: Tuple[Resource, Overlay]):
    return (
        is_resource_in_entries(ro[1].prefer_resources, ro[0]),
        partition_to_priority(ro[1].partition),
        ro[1].priority,
    )


def resource_sort_key(ro: Tuple[Resource, Overlay]):
    return (
        # Preferred resources first
        not is_resource_in_entries(ro[1].prefer_resources, ro[0]),
        # Partition priority
        -partition_to_priority(ro[1].partition),
        # Overlay priority
        -ro[1].priority,
        # Package name
        ro[1].package,
    )


def remove_overlays_shadowed_resources(
    overlays: List[Overlay],
    remove_identical: bool,
):
    undetermined_resource_priorities: Dict[
        Tuple[
            # relative path
            str,
            # reference name
            str,
        ],
        # package names
        List[str],
    ] = {}
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
                Overlay,
            ],
        ],
    ] = {}

    def add_undetermined(
        resources: List[
            Tuple[
                Resource,
                Overlay,
            ],
        ],
    ):
        if len(resources) < 2:
            return

        undetermined_resource_priorities.setdefault(
            (
                resources[0][0].rel_path,
                resources[0][0].reference_name,
            ),
            [],
        ).extend(r[1].package for r in resources)

    for overlay in overlays:
        for resource in overlay.resources:
            resource_map.setdefault(
                (
                    overlay.target_package,
                    overlay.attrs_key(),
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
        resources.sort(key=resource_sort_key)

        preferred_resource_overlay = resources[0]
        preferred_resource = resources[0][0]
        preferred_overlay = resources[0][1]
        preferred_resource_equality_key = resource_equality_key(
            preferred_resource_overlay,
        )

        num_equal_preferred_resources = 0
        preferred_resources: List[
            Tuple[
                Resource,
                Overlay,
            ],
        ] = []
        for ro in resources:
            if resource_equality_key(ro) != preferred_resource_equality_key:
                break

            if ro[0] == preferred_resource:
                num_equal_preferred_resources += 1

            preferred_resources.append(ro)

        # If all undetermined priority resources are equal then keep
        # the one in the first overlay (alphabetically)
        if (
            num_equal_preferred_resources != len(preferred_resources)
            and len(preferred_resources) > 1
        ):
            add_undetermined(preferred_resources)

        # If we shadowed an immutable resource, do not check if the
        # preferred resource is identical to AOSP, as we cannot remove
        # it because the immutable shadowed resource would take priority
        shadowed_immutable = False
        shadowed_resources = resources[1:]
        for resource, overlay in shadowed_resources:
            if overlay.immutable:
                shadowed_immutable = True
                continue

            overlay.removed_resources.add(resource)

        if shadowed_immutable or not remove_identical:
            continue

        if (
            preferred_overlay.package_resources is not None
            and preferred_resource in preferred_overlay.package_resources
        ):
            preferred_overlay.removed_resources.add(preferred_resource)

    for overlay in overlays:
        keep_referenced_resources_from_removal(
            overlay.removed_resources,
            overlay.resources,
        )

        overlay.resources.remove_many(overlay.removed_resources)
        overlay.removed_resources.clear()

    return undetermined_resource_priorities

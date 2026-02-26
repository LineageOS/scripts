#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import shutil
from argparse import ArgumentParser
from dataclasses import dataclass
from itertools import chain
from os import path
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, cast

from bp.bp_module import parse_bp_rro_module
from bp.bp_utils import (
    ANDROID_BP_NAME,
    get_module_partition,
)
from rro.manifest import ANDROID_MANIFEST_NAME, parse_overlay_manifest
from rro.process_rro import (
    OverlayPriorityData,
    fixup_rro_resources,
    get_rro_resources,
    get_rro_target_package_resources,
    remove_rro_resources,
    remove_rros_shadowed_resources,
    write_rro,
)
from rro.resources import (
    RESOURCES_DIR,
    ResourceMap,
    read_xml_resources_prefix,
)
from rro.target_package import append_extra_locations
from utils.utils import Color, color_print, get_dirs_with_file


@dataclass
class OverlayData:
    name: str
    path: Path
    partition: str
    manifest_name: str
    manifest_path: Path
    module_priority: int
    package: str
    target_package: str
    attrs: Dict[str, str]
    resources: ResourceMap
    package_resources: Optional[ResourceMap]
    immutable: bool


def parse_resource_entries(
    resource_entries_raw: List[str],
    allow_empty_package: bool = True,
):
    resource_entries: Set[Tuple[None | str, str]] = set()

    for resource_entry_raw in resource_entries_raw:
        resource_entry_parts = resource_entry_raw.split(':')
        assert len(resource_entry_parts) <= 2, resource_entry_raw

        if not allow_empty_package and len(resource_entry_parts) != 2:
            raise ValueError(f'Invalid entry: {resource_entry_raw}')

        if len(resource_entry_parts) == 1:
            resource_entries.add((None, resource_entry_raw))
        elif len(resource_entry_parts) == 2:
            target_package, resource_entry_raw = resource_entry_raw.split(':')
            resource_entries.add((target_package, resource_entry_raw))

    return resource_entries


def filter_resource_entries(
    resource_entries: Set[Tuple[None | str, str]],
    target_package: str,
):
    return frozenset(
        resource_name
        for package, resource_name in resource_entries
        if package is None or package == target_package
    )


def remove_shadowed_resources(
    overlays_data: List[OverlayData],
    prefer_resources: Set[Tuple[Optional[str], str]],
):
    undetermined_resource_priorities = remove_rros_shadowed_resources(
        [
            OverlayPriorityData(
                package=o.package,
                target_package=o.target_package,
                partition=o.partition,
                priority=o.module_priority,
                resources=o.resources,
                package_resources=o.package_resources,
                prefer_resources=filter_resource_entries(
                    prefer_resources,
                    o.package,
                ),
                attrs=o.attrs,
                immutable=o.immutable,
            )
            for o in overlays_data
        ]
    )

    for undetermined_resource_priority in undetermined_resource_priorities:
        color_print(
            f'Resource {undetermined_resource_priority[0]} has '
            'undetermined priority between packages: '
            f'{", ".join(undetermined_resource_priority[1])}',
            color=Color.RED,
        )

    if undetermined_resource_priorities:
        raise ValueError('An undetermined priority has been found')


def write_beautified_overlay(
    overlay_data: OverlayData,
    remove_resources: Set[Tuple[None | str, str]],
    keep_resources: Set[Tuple[None | str, str]],
    maintain_copyrights: bool,
):
    target_package_remove_resources = filter_resource_entries(
        remove_resources,
        overlay_data.target_package,
    )
    target_package_keep_resources = filter_resource_entries(
        keep_resources,
        overlay_data.target_package,
    )

    try:
        remove_rro_resources(
            package=overlay_data.package,
            target_package=overlay_data.target_package,
            manifest_path=str(overlay_data.manifest_path),
            resources=overlay_data.resources,
            package_resources=overlay_data.package_resources,
            remove_resources=target_package_remove_resources,
            keep_resources=target_package_keep_resources,
        )

        # Preserve existing res/values/*.xml headers BEFORE we delete res/
        preserved_prefixes: Dict[str, bytes] = {}
        if maintain_copyrights:
            preserved_prefixes = read_xml_resources_prefix(
                overlay_data.resources,
                str(overlay_data.path),
                extra_paths=[overlay_data.manifest_name],
            )

        shutil.rmtree(overlay_data.path, ignore_errors=True)
        Path(overlay_data.path).mkdir(parents=True, exist_ok=True)

        write_rro(
            overlay_data.resources,
            str(overlay_data.path),
            overlay_data.name,
            overlay_data.package,
            overlay_data.target_package,
            overlay_data.attrs,
            preserved_prefixes=preserved_prefixes,
            partition=overlay_data.partition,
        )
    except ValueError as e:
        shutil.rmtree(overlay_data.path, ignore_errors=True)
        color_print(e, color=Color.RED)


def beautify_rro_main():
    parser = ArgumentParser(
        prog='beautify_rro',
        description='Beautify RROs',
    )

    parser.add_argument('overlay_path')
    parser.add_argument('extra_package_locations', nargs='*')
    parser.add_argument(
        '--maintain-copyrights',
        action='store_true',
        help='Preserve existing copyright headers',
    )
    parser.add_argument(
        '--ignore-packages',
        default='',
        help='Comma-separated list of overlay folder names or Android.bp module names to ignore',
    )
    parser.add_argument(
        '-p',
        '--prefer-resource',
        help='Prefer a resource from a specific package when more than one has '
        'the same partition and priority (eg: android:config_defaultAssistant)',
        default=[],
        action='append',
    )
    parser.add_argument(
        '-r',
        '--remove-resource',
        help='Remove a resource by name '
        '(eg: config_defaultAssistant, or android:config_defaultAssistant)',
        default=[],
        action='append',
    )
    parser.add_argument(
        '-s',
        '--keep-resource',
        help='Keep a resource by name, '
        'even if it is not found in the base package and not referenced',
        default=[],
        action='append',
    )
    parser.add_argument(
        '-k',
        '--keep-package',
        help='Keep overlays targeting a package even if it is not found',
        default=[],
        action='append',
    )
    parser.add_argument(
        '-c',
        '--common',
        help='Path to common resources',
        default=[],
        action='append',
    )

    args = parser.parse_args()
    ignore_packages = cast(str, args.ignore_packages)
    remove_resources_raw = cast(List[str], args.remove_resource)
    keep_packages = set(cast(List[str], args.keep_package))
    keep_resources_raw = cast(List[str], args.keep_resource)
    prefer_resources_raw = cast(List[str], args.prefer_resource)

    remove_resources = parse_resource_entries(remove_resources_raw)
    keep_resources = parse_resource_entries(keep_resources_raw)
    prefer_resources = parse_resource_entries(prefer_resources_raw)

    common_paths: List[str] = args.common

    append_extra_locations(args.extra_package_locations)

    ignore_packages = {
        s.strip() for s in ignore_packages.split(',') if s.strip()
    }

    overlays_data: List[OverlayData] = []

    def parse_overlay(overlay_dir: str, immutable: bool):
        overlay_path = Path(overlay_dir)

        android_bp_path = Path(overlay_path, ANDROID_BP_NAME)
        statement = parse_bp_rro_module(android_bp_path)

        module_name = statement['name']
        dir_name = path.basename(overlay_dir)

        if ignore_packages and (
            (module_name and module_name in ignore_packages)
            or (dir_name and dir_name in ignore_packages)
        ):
            return

        manifest = statement.get('manifest', ANDROID_MANIFEST_NAME)
        manifest_path = Path(overlay_dir, manifest)

        resources_dir = statement.get('resource_dirs', [RESOURCES_DIR])[0]
        resources_path = Path(overlay_path, resources_dir)

        package, target_package, overlay_attrs = parse_overlay_manifest(
            str(manifest_path),
        )
        module_partition = get_module_partition(statement)
        module_priority = int(overlay_attrs.get('priority', 0))

        try:
            resources = get_rro_resources(
                package,
                str(resources_path),
            )
            package_resources = get_rro_target_package_resources(
                package=package,
                target_package=target_package,
                resources=resources,
                allow_missing=target_package in keep_packages,
            )
        except ValueError as e:
            shutil.rmtree(overlay_path, ignore_errors=True)
            color_print(e, color=Color.RED)
            return

        fixup_rro_resources(
            package=package,
            resources=resources,
            package_resources=package_resources,
        )

        overlay_data = OverlayData(
            name=module_name,
            path=overlay_path,
            partition=module_partition,
            manifest_name=manifest,
            manifest_path=manifest_path,
            module_priority=module_priority,
            package=package,
            target_package=target_package,
            attrs=overlay_attrs,
            resources=resources,
            package_resources=package_resources,
            immutable=immutable,
        )
        overlays_data.append(overlay_data)

    for overlay_dir in get_dirs_with_file(args.overlay_path, ANDROID_BP_NAME):
        parse_overlay(overlay_dir, immutable=False)

    for overlay_dir in chain(
        *(get_dirs_with_file(c, ANDROID_BP_NAME) for c in common_paths)
    ):
        parse_overlay(overlay_dir, immutable=True)

    remove_shadowed_resources(overlays_data, prefer_resources)

    for overlay_data in overlays_data:
        write_beautified_overlay(
            overlay_data,
            remove_resources=remove_resources,
            keep_resources=keep_resources,
            maintain_copyrights=args.maintain_copyrights,
        )


if __name__ == '__main__':
    beautify_rro_main()

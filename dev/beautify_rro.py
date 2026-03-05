#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import shutil
from argparse import ArgumentParser
from collections import defaultdict
from itertools import chain
from pathlib import Path
from typing import (
    DefaultDict,
    List,
    Optional,
    Set,
    cast,
)

from bp.bp_utils import (
    ANDROID_BP_NAME,
)
from rro.overlay import (
    Overlay,
    fixup_overlay_resources,
    parse_overlay_from_android_bp,
    parse_overlay_target_package_resources,
    remove_overlay_missing_resources,
    remove_overlay_resources,
    remove_overlays_shadowed_resources,
    write_overlay,
)
from rro.resource_map import PackageDirNamesIndex
from rro.resources import filter_resource_entries
from rro.target_package import (
    append_extra_locations,
    map_packages,
    read_package_map,
)
from utils.utils import Color, color_print, get_dirs_with_file


def parse_resource_entries(
    resource_entries_raw: List[str],
    allow_empty_package: bool = True,
):
    resource_entries: DefaultDict[Optional[str], Set[str]] = defaultdict(set)

    for resource_entry_raw in resource_entries_raw:
        resource_entry_parts = resource_entry_raw.split(':')
        assert len(resource_entry_parts) <= 2, resource_entry_raw

        if not allow_empty_package and len(resource_entry_parts) != 2:
            raise ValueError(f'Invalid entry: {resource_entry_raw}')

        if len(resource_entry_parts) == 1:
            resource_entries[None].add(resource_entry_raw)
        elif len(resource_entry_parts) == 2:
            target_package, resource_entry_raw = resource_entry_raw.split(':')
            resource_entries[target_package].add(resource_entry_raw)

    return resource_entries


def remove_shadowed_resources(
    overlays: List[Overlay],
    remove_identical: bool,
    prefer_resources: DefaultDict[Optional[str], Set[str]],
):
    undetermined_resource_priorities = remove_overlays_shadowed_resources(
        overlays=overlays,
        remove_identical=remove_identical,
        prefer_resources=prefer_resources,
    )

    sorted_undetermined = sorted(
        undetermined_resource_priorities.items(),
        key=lambda v: v[0],
    )
    for (rel_path, reference_name), packages in sorted_undetermined:
        color_print(
            f'Resource {rel_path}: {reference_name} has '
            'undetermined priority between packages: '
            f'{", ".join(packages)}',
            color=Color.RED,
        )


def write_beautified_overlay(
    overlay: Overlay,
    remove_resources: DefaultDict[Optional[str], Set[str]],
    keep_resources: DefaultDict[Optional[str], Set[str]],
):
    target_package_remove_resources = filter_resource_entries(
        remove_resources,
        overlay.target_package,
    )

    target_package_keep_resources = filter_resource_entries(
        keep_resources,
        overlay.target_package,
    )

    remove_overlay_resources(
        overlay,
        remove_resources=target_package_remove_resources,
    )

    remove_overlay_missing_resources(
        overlay,
        keep_resources=target_package_keep_resources,
    )

    shutil.rmtree(overlay.path, ignore_errors=True)

    if not overlay.resources:
        color_print(
            f'{overlay.package}: No resources left in overlay',
            color=Color.RED,
        )
        return

    write_overlay(overlay)


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
        '--remove-identical',
        help='Remove resources identical to AOSP '
        '(do not use for overlays that have been commonized)',
        action='store_true',
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
    parser.add_argument(
        '-m',
        '--package-map',
        help='Path to cached package map',
        type=Path,
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

    if args.package_map is not None:
        package_map = read_package_map(args.package_map)
    else:
        package_map = map_packages()

    ignore_packages = {
        s.strip() for s in ignore_packages.split(',') if s.strip()
    }

    overlays: List[Overlay] = []
    package_dir_names = PackageDirNamesIndex()

    for overlay_dir in get_dirs_with_file(args.overlay_path, ANDROID_BP_NAME):
        overlay = parse_overlay_from_android_bp(
            Path(overlay_dir),
            ignore_packages=ignore_packages,
            package_dir_names=package_dir_names,
            maintain_copyrights=args.maintain_copyrights,
        )
        if overlay is None:
            continue

        overlays.append(overlay)

    for overlay_dir in chain(
        *(get_dirs_with_file(c, ANDROID_BP_NAME) for c in common_paths)
    ):
        overlay = parse_overlay_from_android_bp(
            Path(overlay_dir),
            immutable=True,
            track_index=False,
            ignore_packages=ignore_packages,
            package_dir_names=package_dir_names,
            maintain_copyrights=args.maintain_copyrights,
        )
        if overlay is None:
            continue

        overlays.append(overlay)

    # Parse target package resources in a different loop to assure that we
    # gathered all needed directory and resource names
    remaining_overlays: List[Overlay] = []
    for overlay in overlays:
        parse_overlay_target_package_resources(
            package_map=package_map,
            overlay=overlay,
        )

        if (
            overlay.package_resources is not None
            or overlay.target_package in keep_packages
        ):
            remaining_overlays.append(overlay)
            continue

        color_print(
            f'{overlay.package}: Unknown package name {overlay.target_package}',
            color=Color.RED,
        )

    overlays = remaining_overlays

    for overlay in overlays:
        fixup_overlay_resources(overlay)

    remove_shadowed_resources(
        overlays,
        remove_identical=args.remove_identical,
        prefer_resources=prefer_resources,
    )

    for overlay in overlays:
        if overlay.immutable:
            continue

        write_beautified_overlay(
            overlay,
            remove_resources,
            keep_resources,
        )


if __name__ == '__main__':
    beautify_rro_main()

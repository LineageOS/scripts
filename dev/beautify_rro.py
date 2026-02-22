#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import shutil
from argparse import ArgumentParser
from dataclasses import dataclass
from os import path
from pathlib import Path
from typing import Dict, List, Set, Tuple, cast

from bp.bp_module import BpModule, RROModule
from bp.bp_parser import bp_parser  # type: ignore
from bp.bp_utils import (
    ANDROID_BP_NAME,
    get_module_partition,
    partition_to_priority,
)
from rro.manifest import ANDROID_MANIFEST_NAME, parse_overlay_manifest
from rro.process_rro import parse_rro, write_rro
from rro.resources import read_xml_resources_prefix
from rro.target_package import append_extra_locations
from utils.utils import Color, color_print, get_dirs_with_file


@dataclass
class OverlayData:
    path: str
    partition: str
    module_priority: int
    statement: RROModule


def parse_resource_entries(resource_entries_raw: List[str]):
    resource_entries: Set[Tuple[None | str, str]] = set()

    for resource_entry_raw in resource_entries_raw:
        resource_entry_parts = resource_entry_raw.split(':')
        assert len(resource_entry_parts) <= 2, resource_entry_raw

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

    args = parser.parse_args()
    ignore_packages = cast(str, args.ignore_packages)
    remove_resources_raw = cast(List[str], args.remove_resource)
    keep_packages = set(cast(List[str], args.keep_package))
    keep_resources_raw = cast(List[str], args.keep_resource)

    remove_resources = parse_resource_entries(remove_resources_raw)
    keep_resources = parse_resource_entries(keep_resources_raw)

    append_extra_locations(args.extra_package_locations)

    ignore_packages = {
        s.strip() for s in ignore_packages.split(',') if s.strip()
    }

    overlays_data: List[OverlayData] = []

    for dir_path in get_dirs_with_file(args.overlay_path, ANDROID_BP_NAME):
        android_bp_path = path.join(dir_path, ANDROID_BP_NAME)

        with open(android_bp_path, 'r') as android_bp:
            for statement in bp_parser.parse(android_bp.read()):  # type: ignore
                statement = cast(BpModule, statement)

                if statement['module'] != 'runtime_resource_overlay':
                    continue

                statement = cast(RROModule, statement)

                module_name = statement['name']
                dir_name = path.basename(dir_path)

                if ignore_packages and (
                    (module_name and module_name in ignore_packages)
                    or (dir_name and dir_name in ignore_packages)
                ):
                    continue

                manifest = statement.get('manifest', ANDROID_MANIFEST_NAME)
                manifest_path = path.join(dir_path, manifest)
                _, _, overlay_attrs = parse_overlay_manifest(
                    manifest_path,
                )
                module_partition = get_module_partition(statement)
                module_priority = int(overlay_attrs.get('priority', 0))

                overlay_data = OverlayData(
                    path=dir_path,
                    partition=module_partition,
                    module_priority=module_priority,
                    statement=statement,
                )
                overlays_data.append(overlay_data)

    # Sort RROs in reverse order of priority so we can keep track of what
    # resources have been found, and remove duplicates
    overlays_data.sort(
        key=lambda o: (
            partition_to_priority(o.partition),
            o.module_priority,
            o.path,
        )
    )

    all_packages_resources_map: Dict[
        Tuple[
            # target package name
            str,
            # overlay attributes
            Tuple[Tuple[str, str], ...],
        ],
        Dict[Tuple[str, ...], str],
    ] = {}
    for overlay_data in overlays_data:
        dir_path = overlay_data.path
        statement = overlay_data.statement
        module_name = statement['name']
        manifest = statement.get('manifest', ANDROID_MANIFEST_NAME)
        resources_dir = statement.get('resource_dirs', ['res'])[0]
        partition = get_module_partition(statement)

        manifest_path = path.join(dir_path, manifest)
        package, target_package, overlay_attrs = parse_overlay_manifest(
            manifest_path,
        )

        target_package_remove_resources = filter_resource_entries(
            remove_resources,
            target_package,
        )
        target_package_keep_resources = filter_resource_entries(
            keep_resources,
            target_package,
        )

        overlay_attrs_key = tuple(sorted(overlay_attrs.items()))
        package_resources_map = all_packages_resources_map.setdefault(
            (target_package, overlay_attrs_key), {}
        )
        try:
            overlay_resources = parse_rro(
                dir_path,
                package,
                target_package,
                manifest,
                resources_dir,
                package_resources_map=package_resources_map,
                remove_shadowed_resources=True,
                remove_missing_resources=True,
                remove_resources=target_package_remove_resources,
                keep_packages=keep_packages,
                keep_resources=target_package_keep_resources,
            )

            # Preserve existing res/values/*.xml headers BEFORE we delete res/
            preserved_prefixes: Dict[str, bytes] = {}
            if args.maintain_copyrights:
                preserved_prefixes = read_xml_resources_prefix(
                    overlay_resources,
                    dir_path,
                    extra_paths=[manifest],
                )

            shutil.rmtree(dir_path, ignore_errors=True)
            Path(dir_path).mkdir(parents=True, exist_ok=True)

            write_rro(
                overlay_resources,
                dir_path,
                module_name,
                package,
                target_package,
                overlay_attrs,
                preserved_prefixes=preserved_prefixes,
                partition=partition,
            )
        except ValueError as e:
            shutil.rmtree(dir_path, ignore_errors=True)
            color_print(e, color=Color.RED)


if __name__ == '__main__':
    beautify_rro_main()

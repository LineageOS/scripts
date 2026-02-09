#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import shutil
from argparse import ArgumentParser
from os import path
from typing import Dict, List, Tuple, cast

from bp.bp_module import BpModule, RROModule
from bp.bp_parser import bp_parser  # type: ignore
from bp.bp_utils import (
    ANDROID_BP_NAME,
    get_module_partition,
    partition_to_priority,
)
from rro.manifest import ANDROID_MANIFEST_NAME, parse_overlay_manifest
from rro.process_rro import process_rro
from rro.resources import resources_dict
from rro.target_package import append_extra_locations
from utils.utils import Color, color_print, get_dirs_with_file

if __name__ == '__main__':
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
        help='Remove a resource by name (eg: config_defaultAssistant)',
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
    remove_resources = set(cast(List[str], args.remove_resource))
    keep_packages = set(cast(List[str], args.keep_package))

    append_extra_locations(args.extra_package_locations)

    ignore_packages = set(
        filter(
            lambda s: s,
            map(lambda s: s.strip(), ignore_packages.split(',')),
        )
    )

    rros: List[Tuple[int, int, str, RROModule]] = []

    for dir_path in get_dirs_with_file(args.overlay_path, ANDROID_BP_NAME):
        android_bp_path = path.join(dir_path, ANDROID_BP_NAME)

        with open(android_bp_path, 'r') as android_bp:
            for statement in bp_parser.parse(android_bp.read()):  # type: ignore
                statement = cast(BpModule, statement)

                if statement['module'] != 'runtime_resource_overlay':
                    continue

                statement = cast(RROModule, statement)

                module_name = statement.get('name', '')
                dir_name = path.basename(dir_path)

                if ignore_packages and (
                    (module_name and module_name in ignore_packages)
                    or (dir_name and dir_name in ignore_packages)
                ):
                    continue

                manifest = statement.get('manifest', ANDROID_MANIFEST_NAME)
                manifest_path = path.join(dir_path, manifest)
                package, target_package, overlay_attrs = parse_overlay_manifest(
                    manifest_path,
                )
                module_partition = get_module_partition(statement)
                partition_priority = partition_to_priority(module_partition)
                module_priority = int(overlay_attrs.get('priority', 0))

                rros.append(
                    (
                        partition_priority,
                        module_priority,
                        dir_path,
                        statement,
                    )
                )

    # Sort RROs in reverse order of priority so we can keep track of what
    # resources have been found, and remove duplicates
    sorted_rros = [
        (d, s)
        for *_, d, s in sorted(
            rros,
            key=lambda v: v[:3],
            reverse=True,
        )
    ]

    all_packages_resources_map: Dict[str, resources_dict] = {}
    for dir_path, statement in sorted_rros:
        manifest = statement.get('manifest', ANDROID_MANIFEST_NAME)
        resources_dir = statement.get('resource_dirs', ['res'])[0]

        try:
            process_rro(
                dir_path,
                dir_path,
                manifest,
                resources_dir,
                all_packages_resources_map=all_packages_resources_map,
                maintain_copyrights=args.maintain_copyrights,
                # Identical to AOSP resources cannot be removed without doing
                # priority ordering, so it can only be done while beautifying
                # all possible RROs at the same time
                remove_identical=True,
                remove_resources=remove_resources,
                keep_packages=keep_packages,
            )
        except ValueError as e:
            shutil.rmtree(dir_path, ignore_errors=True)
            color_print(e, color=Color.RED)

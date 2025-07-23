#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
import shutil
from argparse import ArgumentParser
from os import path
from tempfile import TemporaryDirectory

from manifest import (
    ANDROID_MANIFEST_NAME,
    parse_overlay_manifest,
    write_manifest,
)
from resources import (
    group_overlay_resources_rel_path,
    parse_overlay_resources,
    parse_package_resources,
    write_grouped_resources,
)
from target_package import get_target_package_path
from utils import (
    ANDROID_BP_NAME,
    Color,
    color_print,
    get_partition_specific,
    run_cmd,
)


def write_android_bp(apk_path: str, android_bp_path: str, package: str):
    apk_path_parts = apk_path.split('/')

    partition = None
    try:
        overlay_index = apk_path_parts.index('overlay')
        partition = apk_path_parts[overlay_index - 1]
    except (ValueError, IndexError):
        pass

    specific = get_partition_specific(partition)
    if specific is None:
        specific = ''
    else:
        specific = f'\n    {specific}: true,'

    with open(android_bp_path, 'w') as o:
        o.write(
            f'''
//
// SPDX-FileCopyrightText: The LineageOS Project
// SPDX-License-Identifier: Apache-2.0
//

runtime_resource_overlay {{
    name: "{package}",{specific}
}}
'''
        )


def extract_apk(apk_path: str, tmp_dir: str):
    run_cmd(['apktool', 'd', apk_path, '-f', '--no-src', '-o', tmp_dir])


def generate_rro(apk_path: str, output_path: str):
    shutil.rmtree(output_path, ignore_errors=True)
    os.makedirs(output_path, exist_ok=True)

    with TemporaryDirectory() as tmp_dir:
        extract_apk(apk_path, tmp_dir)
        manifest_path = path.join(tmp_dir, ANDROID_MANIFEST_NAME)

        package, target_package, overlay_attrs = parse_overlay_manifest(
            manifest_path,
        )

        overlay_resources = parse_overlay_resources(tmp_dir)
        if not overlay_resources:
            raise ValueError(f'No overlay resources in package {package}')

        target_package_dir, resource_dirs = get_target_package_path(
            target_package
        )
        package_resources = parse_package_resources(
            target_package_dir, resource_dirs
        )

        grouped_resources, missing_resources, identical_resources = (
            group_overlay_resources_rel_path(
                overlay_resources,
                package_resources,
            )
        )

        if not grouped_resources:
            raise ValueError(f'No resources left in package {package}')

        for resource in missing_resources:
            color_print(
                f'Resource {resource.name} not found in package {target_package}',
                color=Color.RED,
            )

        for resource in identical_resources:
            color_print(
                f'Resource {resource.name} identical in package {target_package}',
                color=Color.YELLOW,
            )

        write_grouped_resources(grouped_resources, output_path)

        rro_manifest_path = path.join(output_path, ANDROID_MANIFEST_NAME)
        write_manifest(
            rro_manifest_path, package, target_package, overlay_attrs
        )
        android_bp_path = path.join(output_path, ANDROID_BP_NAME)
        write_android_bp(
            apk_path,
            android_bp_path,
            package,
        )


def get_apks(overlays_path: str):
    for dir_path, _, file_names in os.walk(overlays_path):
        for file_name in file_names:
            _, ext = path.splitext(file_name)
            if ext != '.apk':
                continue

            apk_path = path.join(dir_path, file_name)
            yield apk_path


if __name__ == '__main__':
    parser = ArgumentParser(
        prog='generate_rro',
        description='Generate RROs',
    )

    parser.add_argument('apk_path')
    parser.add_argument(
        '-n',
        '--name',
        help='Name of overlay',
    )
    parser.add_argument(
        '-o',
        '--overlays',
        help='Path to overlays directory',
        default='./overlays',
    )

    args = parser.parse_args()

    overlays_path: str = args.overlays
    rro_names = []

    if path.isdir(args.apk_path):
        apk_paths = list(get_apks(args.apk_path))
        if args.name is not None:
            rro_names = [args.name]
    elif path.isfile(args.apk_path):
        apk_paths = [args.apk_path]
    else:
        raise ValueError(f'Invalid file: {args.apk_path}')

    if not rro_names:
        for apk_path in apk_paths:
            apk_name = path.basename(apk_path)
            rro_name, ext = path.splitext(apk_name)
            rro_names.append(rro_name)

    for apk_path, rro_name in zip(apk_paths, rro_names):
        output_path = path.join(overlays_path, rro_name)
        try:
            generate_rro(apk_path, output_path)
        except ValueError as e:
            shutil.rmtree(output_path, ignore_errors=True)
            print(e)

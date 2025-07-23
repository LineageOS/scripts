#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from argparse import ArgumentParser
from os import path

from manifest import ANDROID_MANIFEST_NAME, parse_overlay_manifest
from resources import (
    group_overlay_resources_rel_path,
    parse_overlay_resources,
    parse_package_resources,
    remove_overlay_resources,
    write_grouped_resources,
)
from target_package import get_target_package_path
from utils import ANDROID_BP_NAME, Color, color_print, get_dirs_with_file


def beautify_rro(rro_path: str):
    manifest_path = path.join(rro_path, ANDROID_MANIFEST_NAME)

    package, target_package, _ = parse_overlay_manifest(
        manifest_path,
    )

    overlay_resources = parse_overlay_resources(rro_path)
    if not overlay_resources:
        raise ValueError(f'No overlay resources in package {package}')

    target_package_dir, resource_dirs = get_target_package_path(target_package)
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

    remove_overlay_resources(rro_path)
    write_grouped_resources(grouped_resources, rro_path)


if __name__ == '__main__':
    parser = ArgumentParser(
        prog='beautify_rro',
        description='Beautify RROs',
    )

    parser.add_argument('overlay_path')

    args = parser.parse_args()

    for dir_path in get_dirs_with_file(args.overlay_path, ANDROID_BP_NAME):
        beautify_rro(dir_path)

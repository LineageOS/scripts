# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import functools
from os import path
from typing import Dict, List, Tuple

from bp.bp_parser import bp_parser
from bp.bp_utils import ANDROID_BP_NAME, bp_extend_defaults
from rro.manifest import parse_package_manifest
from utils.utils import (
    Color,
    android_root,
    color_print,
    get_files_with_name,
)

PACKAGE_LOCATIONS = [
    'frameworks/base/core/res',
    'frameworks/base/packages',
    'lineage-sdk',
    'packages',
]


def get_existing_paths_rel(root_path: str, rel_paths: List[str]):
    full_paths = map(lambda m: path.join(root_path, m), rel_paths)
    filtered_paths = filter(lambda m: path.exists(m), full_paths)
    return list(filtered_paths)


def get_app_manifests(app_module: Dict):
    manifests = []

    manifest = app_module.get('manifest', 'AndroidManifest.xml')
    manifests.append(manifest)

    additional_manifests = app_module.get('additional_manifests', [])
    manifests.extend(additional_manifests)

    return manifests


def get_app_resources(android_bp_dir_path: str, app_module: Dict):
    resource_dirs = app_module.get('resource_dirs', ['res'])
    return get_existing_paths_rel(android_bp_dir_path, resource_dirs)


def get_app_package_name(android_bp_dir_path: str, app_module: Dict):
    manifests = get_app_manifests(app_module)
    for manifest_path in get_existing_paths_rel(android_bp_dir_path, manifests):
        package_name = parse_package_manifest(manifest_path)
        if package_name is not None:
            return package_name

    return None


@functools.cache
def map_packages():
    defaults_map = {}
    android_apps_map = {}

    for parent_path in PACKAGE_LOCATIONS:
        packages_path = path.join(android_root, parent_path)

        for android_bp_path in get_files_with_name(
            packages_path,
            ANDROID_BP_NAME,
            skipped_directory_names=set(['tests']),
        ):
            android_bp_dir_path = path.dirname(android_bp_path)

            with open(android_bp_path, 'r') as android_bp:
                text = android_bp.read()
                try:
                    result = bp_parser.parse(text)
                except SyntaxError as e:
                    color_print(
                        f'Failed to parse blueprint {android_bp_path}',
                        color=Color.YELLOW,
                    )
                    continue

            for statement in result:
                if 'module' not in statement:
                    continue

                if 'name' in statement:
                    name = statement['name']

                if statement['module'] == 'java_defaults':
                    # TODO: some defaults extend java_defaults via soong_config_module_type
                    assert name not in defaults_map
                    defaults_map[name] = statement

                if (
                    statement['module'] == 'android_app'
                    or statement['module'] == 'android_library'
                ):
                    assert name not in android_apps_map
                    android_apps_map[name] = (
                        android_bp_dir_path,
                        statement,
                    )

    package_path_map: Dict[str, List[Tuple[str, Tuple[str]]]] = {}
    for android_bp_dir_path, app_module in android_apps_map.values():
        defaults = app_module.get('defaults', [])
        app_module, missing_defaults = bp_extend_defaults(
            app_module,
            defaults,
            defaults_map,
        )

        name = app_module['name']

        package_name = get_app_package_name(
            android_bp_dir_path,
            app_module,
        )

        resource_dirs = get_app_resources(
            android_bp_dir_path,
            app_module,
        )

        if missing_defaults:
            color_print(
                f'Failed to find defaults for app {name}, '
                f'package name: {package_name}',
                missing_defaults,
                color=Color.YELLOW,
            )

        if package_name is None:
            color_print(
                f'Failed to find package name for app {name}',
                color=Color.YELLOW,
            )
            continue

        if not resource_dirs:
            # color_print(
            #     f'Failed to find resource dirs for app {name}, '
            #     f'package name: {package_name}',
            #     color=Color.YELLOW,
            # )
            continue

        package_path_map.setdefault(package_name, []).append(
            (
                android_bp_dir_path,
                tuple(resource_dirs),
            )
        )

    return package_path_map


target_package_map = {
    'com.android.systemui': 'com.android.systemui.res',
}

target_package_name_map = {
    'com.google.android.wifi.resources': 'com.android.wifi.resources',
    'com.google.android.connectivity.resources': 'com.android.connectivity.resources',
    'com.google.android.networkstack': 'com.android.networkstack',
    'com.google.android.networkstack.tethering': 'com.android.networkstack.tethering',
    'com.google.android.permissioncontroller': 'com.android.permissioncontroller',
}


def get_target_packages(target_package: str):
    package_path_map = map_packages()
    new_target_package = target_package

    # Multiple apps match the com.android.systemui package name
    # and the one we're interested in doesn't actually have any
    # resource dirs. Redirect it to the .res package.
    if target_package in target_package_map:
        target_package = target_package_map[target_package]

    # Some apps have equivalents in AOSP with a different package name
    if (
        target_package not in package_path_map
        and target_package in target_package_name_map
    ):
        target_package = target_package_name_map[target_package]
        new_target_package = target_package

    if target_package not in package_path_map:
        raise ValueError(f'Unknown package name: {target_package}')

    return package_path_map[target_package], new_target_package

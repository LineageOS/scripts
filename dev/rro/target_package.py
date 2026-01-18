# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from os import path
from pathlib import Path
from typing import Dict, List, Set, Tuple, cast

from bp.bp_module import (
    AppModule,
    BpModule,
    FilegroupModule,
    SoongConfigModuleTypeModule,
)
from bp.bp_parser import bp_parser  # type: ignore
from bp.bp_utils import ANDROID_BP_NAME, bp_extend_defaults
from rro.manifest import ANDROID_MANIFEST_NAME, parse_package_manifest
from rro.resources import RESOURCES_DIR
from utils.utils import (
    Color,
    android_root,
    color_print,
    get_files_with_name,
)

PACKAGE_LOCATIONS = [
    'frameworks/base/core/res',
    'frameworks/base/packages',
    'frameworks/base/libs',
    'lineage-sdk',
    'packages',
]


def append_extra_locations(package_locations: List[str]):
    PACKAGE_LOCATIONS.extend(package_locations)


def get_existing_paths_rel(root_path: str, rel_paths: List[str]):
    full_paths = map(lambda m: path.join(root_path, m), rel_paths)
    filtered_paths = filter(lambda m: path.exists(m), full_paths)
    return list(filtered_paths)


def resolve_manifest_filegroups(
    manifests: List[str],
    filegroups_map: Dict[str, FilegroupModule],
):
    resolved_manifests: List[str] = []

    for manifest in manifests:
        if not manifest.startswith(':'):
            resolved_manifests.append(manifest)
            continue

        filegroup_name = manifest[1:]
        if filegroup_name not in filegroups_map:
            color_print(
                f'Failed to find filegroup {filegroup_name}',
                color=Color.YELLOW,
            )
            continue

        filegroup_module = filegroups_map[filegroup_name]
        resolved_manifests.extend(filegroup_module['srcs'])

    return resolved_manifests


def get_app_manifests(
    app_module: AppModule,
    filegroups_map: Dict[str, FilegroupModule],
):
    manifests: List[str] = []

    manifest = app_module.get('manifest', ANDROID_MANIFEST_NAME)
    manifests.append(manifest)

    additional_manifests = app_module.get('additional_manifests', [])
    manifests.extend(additional_manifests)

    return resolve_manifest_filegroups(manifests, filegroups_map)


def get_app_resources(
    android_apps_map: Dict[str, Tuple[str, AppModule]],
    android_bp_dir_path: str,
    app_module: AppModule,
    missing_libs: Set[str],
    resource_dirs: List[str],
):
    if 'static_libs' in app_module:
        for lib_name in app_module['static_libs']:
            if lib_name not in android_apps_map:
                if lib_name in missing_libs:
                    continue

                missing_libs.add(lib_name)

                # color_print(
                #     f'Failed to find static lib {lib_name} '
                #     f'for app {app_module['name']}',
                #     color=Color.YELLOW,
                # )
                continue

            lib_android_bp_dir_path = android_apps_map[lib_name][0]
            lib_module = android_apps_map[lib_name][1]
            get_app_resources(
                android_apps_map,
                lib_android_bp_dir_path,
                lib_module,
                missing_libs,
                resource_dirs,
            )

    local_resource_dirs = app_module.get('resource_dirs', [RESOURCES_DIR])
    local_resource_dirs = get_existing_paths_rel(
        android_bp_dir_path,
        local_resource_dirs,
    )
    for resource_dir in local_resource_dirs:
        if resource_dir not in resource_dirs:
            resource_dirs.append(resource_dir)


def get_app_package_name(android_bp_dir_path: str, manifests: List[str]):
    for manifest_path in get_existing_paths_rel(android_bp_dir_path, manifests):
        package_name = parse_package_manifest(manifest_path)
        if package_name is not None:
            return package_name

    return None


@dataclass
class PackageMap:
    packages: Dict[
        # package name
        str,
        # targets
        List[
            Tuple[
                # root directory
                str,
                # target name
                str,
                # resource directories
                List[str],
            ],
        ],
    ]
    rros: Dict[
        # target name
        str,
        Tuple[
            str,
            BpModule,
        ],
    ]


def map_packages():
    soong_config_module_types = set(['java_defaults'])
    defaults_map: Dict[str, BpModule] = {}
    android_apps_map: Dict[str, Tuple[str, AppModule]] = {}
    android_libraries_map: Dict[str, Tuple[str, AppModule]] = {}
    filegroups_map: Dict[str, FilegroupModule] = {}
    missing_libs: Set[str] = set()

    package_map = PackageMap(
        packages={},
        rros={},
    )

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
                    result = cast(List[BpModule], bp_parser.parse(text))  # type: ignore
                except SyntaxError:
                    color_print(
                        f'Failed to parse blueprint {android_bp_path}',
                        color=Color.YELLOW,
                    )
                    continue

            for statement in result:
                if 'module' not in statement:
                    continue

                if 'name' not in statement:
                    continue

                name = statement['name']
                assert isinstance(name, str)

                if statement['module'] in soong_config_module_types:
                    # TODO: some defaults extend java_defaults via soong_config_module_type
                    assert name not in defaults_map
                    defaults_map[name] = statement

                if statement['module'] == 'filegroup':
                    assert name not in filegroups_map
                    statement = cast(FilegroupModule, statement)
                    filegroups_map[name] = statement

                if statement['module'] == 'soong_config_module_type':
                    statement = cast(SoongConfigModuleTypeModule, statement)
                    if statement['module_type'] == 'java_defaults':
                        soong_config_module_types.add(name)

                if statement['module'] == 'android_app':
                    assert name not in android_apps_map
                    statement = cast(AppModule, statement)
                    android_apps_map[name] = (
                        android_bp_dir_path,
                        statement,
                    )
                elif statement['module'] == 'android_library':
                    assert name not in android_libraries_map
                    statement = cast(AppModule, statement)
                    android_libraries_map[name] = (
                        android_bp_dir_path,
                        statement,
                    )

                if statement['module'] == 'runtime_resource_overlay':
                    package_map.rros[name] = (
                        android_bp_dir_path,
                        statement,
                    )

    package_set: Set[
        Tuple[
            # root directory
            str,
            # target name
            str,
            # resource directories
            Tuple[str, ...],
        ]
    ] = set()
    for android_bp_dir_path, app_module in android_apps_map.values():
        defaults = app_module.get('defaults', [])

        app_module, missing_defaults = bp_extend_defaults(
            app_module,
            defaults,
            defaults_map,
        )
        app_module = cast(AppModule, app_module)

        name = app_module['name']

        manifests = get_app_manifests(app_module, filegroups_map)

        package_name = get_app_package_name(
            android_bp_dir_path,
            manifests,
        )

        resource_dirs: List[str] = []
        get_app_resources(
            android_libraries_map,
            android_bp_dir_path,
            app_module,
            missing_libs,
            resource_dirs,
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

        package_path_set_entry = (
            android_bp_dir_path,
            package_name,
            tuple(resource_dirs),
        )
        if package_path_set_entry in package_set:
            continue

        package_set.add(package_path_set_entry)

        package_map.packages.setdefault(package_name, []).append(
            (
                android_bp_dir_path,
                name,
                resource_dirs,
            )
        )

    return package_map


target_package_name_map = {
    'com.google.android.apps.nexuslauncher': 'com.android.launcher3',
    'com.google.android.avatarpicker': 'com.android.avatarpicker',
    'com.google.android.captiveportallogin': 'com.android.captiveportallogin',
    'com.google.android.cellbroadcastreceiver': 'com.android.cellbroadcastreceiver',
    'com.google.android.cellbroadcastservice': 'com.android.cellbroadcastservice',
    'com.google.android.connectivity.resources': 'com.android.connectivity.resources',
    'com.google.android.devicelockcontroller': 'com.android.devicelockcontroller',
    'com.google.android.documentsui': 'com.android.documentsui',
    'com.google.android.healthconnect.controller': 'com.android.healthconnect.controller',
    'com.google.android.networkstack': 'com.android.networkstack',
    'com.google.android.networkstack.tethering': 'com.android.networkstack.tethering',
    'com.google.android.nfc': 'com.android.nfc',
    'com.google.android.permissioncontroller': 'com.android.permissioncontroller',
    'com.google.android.providers.media.module': 'com.android.providers.media.module',
    'com.google.android.storagemanager': 'com.android.storagemanager',
    'com.google.android.uwb.resources': 'com.android.uwb.resources',
    'com.google.android.wifi.resources': 'com.android.wifi.resources',
}


def fixup_target_package(target_package: str):
    if target_package in target_package_name_map:
        return target_package_name_map[target_package]

    return target_package


def get_target_packages(package_map: PackageMap, target_package: str):
    return package_map.packages.get(target_package, [])


def find_overlay_android_bp_path_by_name(package_map: PackageMap, name: str):
    if name in package_map.rros:
        return package_map.rros[name][0]

    return None


def write_package_map(output_path: Path):
    package_map = map_packages()

    with output_path.open('w', encoding='utf-8') as f:
        json.dump(
            asdict(package_map),
            f,
            indent=4,
            ensure_ascii=False,
        )


def read_package_map(input_path: Path):
    with input_path.open('r', encoding='utf-8') as f:
        data = json.load(f)

    return PackageMap(**data)

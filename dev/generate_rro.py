#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
import shutil
from argparse import ArgumentParser
from pathlib import Path
from typing import Dict, List, Optional, Set, cast

from apk.apk_extract import extract_apks
from rro.manifest import ANDROID_MANIFEST_NAME, parse_overlay_manifest
from rro.process_rro import (
    check_rro_matches_aosp,
    fixup_rro_resources,
    get_rro_resources,
    get_rro_target_package_resources,
    simplify_rro_name,
    simplify_rro_package,
    write_rro,
    write_rro_meta,
)
from rro.resources import RESOURCES_DIR, dir_names_to_frozen_dict
from rro.target_package import (
    PackageMap,
    append_extra_locations,
    fixup_target_package,
    map_packages,
    read_package_map,
)
from utils.utils import Color, color_print, run_cmd


def extract_apk(apk_path: Path, tmp_dir: Path):
    run_cmd(
        [
            'apktool',
            'd',
            str(apk_path),
            '-f',
            '--no-src',
            '--keep-broken-res',
            '-o',
            str(tmp_dir),
        ]
    )


def get_apks(overlays_path: Path):
    for dir_path, _, file_names in os.walk(overlays_path):
        for file_name in file_names:
            if Path(file_name).suffix != '.apk':
                continue

            apk_path = Path(dir_path, file_name)
            yield apk_path


def find_apk_partition(apk_path: Path):
    apk_path_parts = apk_path.parts

    partition = None
    try:
        overlay_index = apk_path_parts.index('overlay')
        partition = apk_path_parts[overlay_index - 1]
    except (ValueError, IndexError):
        pass

    return partition


def generate_rro(
    package_map: PackageMap,
    rro_name: str,
    original_rro_name: str,
    package: str,
    target_package: str,
    partition: Optional[str],
    resources_path: Path,
    apk_output_path: Path,
    overlay_attrs: Dict[str, str],
    exclude_overlays: Set[str],
    exclude_packages: Set[str],
    device: Optional[str],
):
    package, original_package = simplify_rro_package(
        package,
        device,
    )
    if package in exclude_overlays:
        raise ValueError(f'{package}: Excluded')
    if original_package in exclude_overlays:
        raise ValueError(f'{original_package}: Excluded')

    target_package, orignal_target_package = fixup_target_package(
        target_package,
    )
    if target_package in exclude_packages:
        raise ValueError(f'{package}: Excluded by {target_package}')

    if orignal_target_package in exclude_packages:
        raise ValueError(f'{package}: Excluded by {orignal_target_package}')

    resources = get_rro_resources(package, str(resources_path))
    package_resources = get_rro_target_package_resources(
        package_map=package_map,
        package=package,
        target_package=target_package,
        resources=resources,
        allow_missing=True,
        parse_all_values=False,
        dir_names=dir_names_to_frozen_dict(resources.dir_names_to_names()),
    )
    fixup_rro_resources(
        package=package,
        resources=resources,
        package_resources=package_resources,
    )
    check_rro_matches_aosp(
        package_map=package_map,
        rro_name=rro_name,
        package=package,
        target_package=target_package,
        resources=resources,
    )

    shutil.rmtree(apk_output_path, ignore_errors=True)
    apk_output_path.mkdir(parents=True, exist_ok=True)

    write_rro(
        resources=resources,
        output_path=str(apk_output_path),
        rro_name=rro_name,
        package=package,
        target_package=target_package,
        overlay_attrs=overlay_attrs,
        partition=partition,
    )
    write_rro_meta(
        output_path=apk_output_path,
        rro_name=original_rro_name,
        package=original_package,
        target_package=orignal_target_package,
        device=device,
    )


def generate_rro_main():
    parser = ArgumentParser(
        prog='generate_rro',
        description='Generate RROs',
    )

    parser.add_argument(
        'apk_path',
        nargs='?',
    )
    parser.add_argument(
        'extra_package_locations',
        nargs='*',
    )
    parser.add_argument(
        '--dump',
        help='Path to dump where to find overlays and frameworks automatically',
        type=Path,
    )
    parser.add_argument(
        '-o',
        '--overlays',
        help='Path to overlays directory',
        default='./overlays',
    )
    parser.add_argument(
        '-e',
        '--exclude-overlay',
        help='Prevent overlay generation for an overlay package name',
        default=[],
        action='append',
    )
    parser.add_argument(
        '-p',
        '--exclude-package',
        help='Prevent overlay generation for a target package',
        default=[],
        action='append',
    )
    parser.add_argument(
        '-f',
        '--framework',
        help='Path to framework-res.apk',
        type=Path,
    )
    parser.add_argument(
        '-d',
        '--device',
        help='Device name to be added to auto-generated RROs',
    )
    parser.add_argument(
        '--apktool',
        help='Use apktool',
        action='store_true',
    )
    parser.add_argument(
        '-m',
        '--package-map',
        help='Path to cached package map',
        type=Path,
    )

    args = parser.parse_args()
    exclude_overlays = set(cast(List[str], args.exclude_overlay))
    exclude_packages = set(cast(List[str], args.exclude_package))

    append_extra_locations(args.extra_package_locations)

    if args.package_map is not None:
        package_map = read_package_map(args.package_map)
    else:
        package_map = map_packages()

    overlays_path = Path(args.overlays)

    framework_path: Optional[Path] = None
    if args.framework is not None:
        framework_path = args.framework

    apk_paths: List[Path] = []
    if args.dump:
        framework_path = Path(args.dump, 'system/framework/framework-res.apk')

        product_overlay_path = Path(args.dump, 'product/overlay')
        apk_paths += get_apks(product_overlay_path)

        vendor_overlay_path = Path(args.dump, 'vendor/overlay')
        apk_paths += get_apks(vendor_overlay_path)
    elif args.apk_path is not None:
        apk_path_arg = Path(args.apk_path)
        if apk_path_arg.is_dir():
            apk_paths += get_apks(apk_path_arg)
        elif apk_path_arg.is_file():
            apk_paths.append(apk_path_arg)
        else:
            raise ValueError(f'Invalid file: {apk_path_arg}')
    else:
        raise ValueError('No input files provided')

    if framework_path is None and not args.apktool:
        raise ValueError('No framework-res.apk provided')

    output_paths: List[Path] = []
    rro_names: List[str] = []
    original_rro_names: List[str] = []
    partitions: List[Optional[str]] = []

    for apk_path in apk_paths:
        partition = find_apk_partition(apk_path)
        partitions.append(partition)

        rro_name, original_rro_name = simplify_rro_name(
            apk_path.stem,
            args.device,
        )
        rro_names.append(rro_name)
        original_rro_names.append(original_rro_name)

        output_path = Path(overlays_path, rro_name)
        output_paths.append(output_path)

    if not args.apktool:
        assert framework_path is not None
        extract_apks(
            apk_paths,
            output_paths,
            framework_path,
        )

    for apk_path, output_path, rro_name, original_rro_name, partition in zip(
        apk_paths,
        output_paths,
        rro_names,
        original_rro_names,
        partitions,
    ):
        if args.apktool:
            extract_apk(apk_path, output_path)

        manifest_path = Path(output_path, ANDROID_MANIFEST_NAME)
        resources_path = Path(output_path, RESOURCES_DIR)

        package, target_package, overlay_attrs = parse_overlay_manifest(
            str(manifest_path),
        )

        try:
            generate_rro(
                package_map=package_map,
                rro_name=rro_name,
                original_rro_name=original_rro_name,
                package=package,
                target_package=target_package,
                partition=partition,
                resources_path=resources_path,
                apk_output_path=output_path,
                overlay_attrs=overlay_attrs,
                exclude_overlays=exclude_overlays,
                exclude_packages=exclude_packages,
                device=args.device,
            )
        except ValueError as e:
            shutil.rmtree(output_path, ignore_errors=True)
            color_print(e, color=Color.RED)


if __name__ == '__main__':
    generate_rro_main()

#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
import shutil
from argparse import ArgumentParser
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, cast

from apk.apk_extract import extract_apks
from bp.bp_utils import ANDROID_BP_NAME, write_android_bp
from rro.overlay import (
    Overlay,
    fixup_overlay_resources,
    is_overlay_aosp,
    parse_overlay_from_android_bp,
    parse_overlay_target_package_resources,
    simplify_overlay_name,
    write_overlay,
)
from rro.resource_map import PackageDirNamesIndex
from rro.target_package import (
    append_extra_locations,
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


@dataclass
class ApkData:
    path: Path
    output_path: Path
    partition: Optional[str]
    name: str
    original_name: str


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

    apks_data: List[ApkData] = []

    for apk_path in apk_paths:
        partition = find_apk_partition(apk_path)

        original_name = apk_path.stem
        name = simplify_overlay_name(
            original_name,
            args.device,
        )

        output_path = Path(overlays_path, name)

        apk_data = ApkData(
            path=apk_path,
            output_path=output_path,
            partition=partition,
            name=name,
            original_name=original_name,
        )
        apks_data.append(apk_data)

    if not args.apktool:
        assert framework_path is not None
        extract_apks(
            [
                (
                    apk_data.path,
                    apk_data.output_path,
                )
                for apk_data in apks_data
            ],
            framework_path,
        )

    overlays: List[Overlay] = []
    package_dir_names = PackageDirNamesIndex()

    for apk_data in apks_data:
        if args.apktool:
            extract_apk(apk_data.path, apk_data.output_path)

        # Write a dummy Android.bp so we can re-use the parsing logic
        android_bp_path = Path(apk_data.output_path, ANDROID_BP_NAME)
        write_android_bp(
            android_bp_path,
            name=apk_data.name,
            aapt_raw=False,
            partition=apk_data.partition,
        )

        overlay = parse_overlay_from_android_bp(
            apk_data.output_path,
            package_dir_names=package_dir_names,
            exclude_overlays=exclude_overlays,
            exclude_packages=exclude_packages,
            original_name=apk_data.original_name,
            device=args.device,
            devices=set([args.device]),
        )
        if overlay is None:
            continue

        overlays.append(overlay)

    for overlay in overlays:
        parse_overlay_target_package_resources(
            package_map=package_map,
            overlay=overlay,
        )
        fixup_overlay_resources(overlay)

    for overlay in overlays:
        shutil.rmtree(overlay.path, ignore_errors=True)

        if is_overlay_aosp(package_map, overlay):
            color_print(
                f'Overlay {overlay.name} identical to AOSP',
                color=Color.GREEN,
            )
            continue

        overlay.path.mkdir(parents=True, exist_ok=True)

        write_overlay(
            overlay,
            # Write meta to allow commonize script to generate its own names
            write_meta=True,
        )


if __name__ == '__main__':
    generate_rro_main()

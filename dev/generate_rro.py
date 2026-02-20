#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
import shutil
from argparse import ArgumentParser
from contextlib import ExitStack
from os import path
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import List, Optional, cast

from apk.apk_extract import extract_apks
from rro.manifest import ANDROID_MANIFEST_NAME, parse_overlay_manifest
from rro.process_rro import (
    check_rro_matches_aosp,
    parse_rro,
    simplify_rro_name,
    simplify_rro_package,
    write_rro,
    write_rro_meta,
)
from rro.target_package import (
    append_extra_locations,
    fixup_target_package,
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
            _, ext = path.splitext(file_name)
            if ext != '.apk':
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


if __name__ == '__main__':
    parser = ArgumentParser(
        prog='generate_rro',
        description='Generate RROs',
    )

    parser.add_argument('apk_path')
    parser.add_argument('extra_package_locations', nargs='*')
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

    args = parser.parse_args()
    exclude_overlays = set(cast(List[str], args.exclude_overlay))
    exclude_packages = set(cast(List[str], args.exclude_package))

    append_extra_locations(args.extra_package_locations)

    overlays_path = Path(args.overlays)

    apk_path_arg = Path(args.apk_path)
    if apk_path_arg.is_dir():
        apk_paths = list(get_apks(apk_path_arg))
    elif apk_path_arg.is_file():
        apk_paths = [apk_path_arg]
    else:
        raise ValueError(f'Invalid file: {apk_path_arg}')

    with ExitStack() as stack:
        output_paths: List[Path] = []
        tmp_output_paths: List[Path] = []
        rro_names: List[str] = []
        original_rro_names: List[str] = []
        partitions: List[Optional[str]] = []

        for apk_path in apk_paths:
            partition = find_apk_partition(apk_path)
            partitions.append(partition)

            tmp_output_path = Path(stack.enter_context(TemporaryDirectory()))
            tmp_output_paths.append(tmp_output_path)

            apk_name = path.basename(apk_path)
            rro_name, ext = path.splitext(apk_name)
            rro_name, original_rro_name = simplify_rro_name(
                rro_name,
                args.device,
            )
            rro_names.append(rro_name)
            original_rro_names.append(original_rro_name)

            output_path = Path(overlays_path, rro_name)
            output_paths.append(output_path)

        if not args.apktool:
            extract_apks(
                apk_paths,
                tmp_output_paths,
                args.framework,
            )

        for apk_path, tmp_dir, rro_name, original_rro_name, partition in zip(
            apk_paths,
            tmp_output_paths,
            rro_names,
            original_rro_names,
            partitions,
        ):
            if args.apktool:
                extract_apk(apk_path, tmp_dir)

            manifest_path = path.join(tmp_dir, ANDROID_MANIFEST_NAME)
            package, target_package, overlay_attrs = parse_overlay_manifest(
                manifest_path,
            )

            package, original_package = simplify_rro_package(
                package,
                args.device,
            )
            if package in exclude_overlays:
                color_print(f'{package}: Excluded', color=Color.YELLOW)
                continue
            if original_package in exclude_overlays:
                color_print(f'{original_package}: Excluded', color=Color.YELLOW)
                continue

            target_package, orignal_target_package = fixup_target_package(
                target_package,
            )
            if target_package in exclude_packages:
                color_print(
                    f'{package}: Excluded by {target_package}',
                    color=Color.YELLOW,
                )
                continue

            if orignal_target_package in exclude_packages:
                color_print(
                    f'{package}: Excluded by {orignal_target_package}',
                    color=Color.YELLOW,
                )
                continue

            apk_output_path = Path(overlays_path, rro_name)
            shutil.rmtree(apk_output_path, ignore_errors=True)
            os.makedirs(apk_output_path, exist_ok=True)

            try:
                overlay_resources = parse_rro(
                    str(tmp_dir),
                    package,
                    target_package,
                )
                check_rro_matches_aosp(
                    rro_name,
                    package,
                    target_package,
                    overlay_resources,
                )
                write_rro(
                    overlay_resources,
                    str(apk_output_path),
                    rro_name,
                    package,
                    target_package,
                    overlay_attrs,
                    partition=partition,
                )
                write_rro_meta(
                    apk_output_path,
                    original_rro_name,
                    original_package,
                    orignal_target_package,
                    args.device,
                )
            except ValueError as e:
                shutil.rmtree(apk_output_path, ignore_errors=True)
                color_print(e, color=Color.RED)

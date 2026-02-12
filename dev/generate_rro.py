#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
import shutil
from argparse import ArgumentParser
from os import path
from typing import List, cast

from rro.process_rro import (
    generate_rro,
    simplify_rro_name,
)
from rro.target_package import (
    append_extra_locations,
)
from utils.utils import Color, color_print


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
    parser.add_argument('extra_package_locations', nargs='*')
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
    parser.add_argument(
        '-k',
        '--keep-package',
        help='Keep overlays targeting a package even if it is not found',
        default=[],
        action='append',
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

    args = parser.parse_args()
    keep_packages = set(cast(List[str], args.keep_package))
    exclude_overlays = set(cast(List[str], args.exclude_overlay))
    exclude_packages = set(cast(List[str], args.exclude_package))

    append_extra_locations(args.extra_package_locations)

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
        rro_name = simplify_rro_name(rro_name)
        output_path = path.join(overlays_path, rro_name)
        try:
            generate_rro(
                apk_path,
                output_path,
                rro_name,
                keep_packages=keep_packages,
                exclude_overlays=exclude_overlays,
                exclude_packages=exclude_packages,
            )
        except ValueError as e:
            shutil.rmtree(output_path, ignore_errors=True)
            color_print(e, color=Color.RED)

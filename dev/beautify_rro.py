#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import shutil
from argparse import ArgumentParser
from os import path

from bp.bp_parser import bp_parser
from bp.bp_utils import ANDROID_BP_NAME
from rro.manifest import ANDROID_MANIFEST_NAME
from rro.process_rro import process_rro
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

    args = parser.parse_args()

    append_extra_locations(args.extra_package_locations)

    ignore_packages = set(
        filter(
            None,
            map(lambda s: s.strip(), args.ignore_packages.split(',')),
        )
    )

    for dir_path in get_dirs_with_file(args.overlay_path, ANDROID_BP_NAME):
        android_bp_path = path.join(dir_path, ANDROID_BP_NAME)

        with open(android_bp_path, 'r') as android_bp:
            for statement in bp_parser.parse(android_bp.read()):
                if statement.get('module') != 'runtime_resource_overlay':
                    continue

                module_name = statement.get('name', '')
                dir_name = path.basename(dir_path)

                if ignore_packages and (
                    (module_name and module_name in ignore_packages)
                    or (dir_name and dir_name in ignore_packages)
                ):
                    continue

                manifest = statement.get('manifest', ANDROID_MANIFEST_NAME)
                resources_dir = statement.get('resource_dirs', ['res'])[0]

                try:
                    process_rro(
                        dir_path,
                        dir_path,
                        manifest,
                        resources_dir,
                        maintain_copyrights=args.maintain_copyrights,
                    )
                except ValueError as e:
                    shutil.rmtree(dir_path, ignore_errors=True)
                    color_print(e, color=Color.RED)

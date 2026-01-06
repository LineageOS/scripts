#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from argparse import ArgumentParser
from os import path

from bp.bp_parser import bp_parser
from bp.bp_utils import ANDROID_BP_NAME
from rro.manifest import ANDROID_MANIFEST_NAME
from rro.process_rro import process_rro
from utils.utils import get_dirs_with_file

if __name__ == '__main__':
    parser = ArgumentParser(
        prog='beautify_rro',
        description='Beautify RROs',
    )

    parser.add_argument('overlay_path')

    args = parser.parse_args()

    for dir_path in get_dirs_with_file(args.overlay_path, ANDROID_BP_NAME):
        android_bp_path = path.join(dir_path, ANDROID_BP_NAME)

        with open(android_bp_path, 'r') as android_bp:
            for statement in bp_parser.parse(android_bp.read()):
                if statement['module'] != 'runtime_resource_overlay':
                    continue

                manifest = statement.get('manifest', ANDROID_MANIFEST_NAME)
                resources_dir = statement.get('resource_dirs', ['res'])[0]

                process_rro(dir_path, dir_path, manifest, resources_dir)

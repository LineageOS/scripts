#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
import shutil
from argparse import ArgumentParser
from os import path
from tempfile import TemporaryDirectory

from bp.bp_utils import ANDROID_BP_NAME
from rro.process_rro import process_rro, write_rro_android_bp
from utils.utils import Color, color_print, run_cmd


def extract_apk(apk_path: str, tmp_dir: str):
    run_cmd(
        [
            'apktool',
            'd',
            apk_path,
            '-f',
            '--no-src',
            '--keep-broken-res',
            '-o',
            tmp_dir,
        ]
    )


def generate_rro(apk_path: str, output_path: str):
    shutil.rmtree(output_path, ignore_errors=True)
    os.makedirs(output_path, exist_ok=True)

    with TemporaryDirectory() as tmp_dir:
        extract_apk(apk_path, tmp_dir)
        package, aapt_raw = process_rro(tmp_dir, output_path)
        android_bp_path = path.join(output_path, ANDROID_BP_NAME)
        write_rro_android_bp(
            apk_path,
            android_bp_path,
            package,
            aapt_raw,
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
            color_print(e, color=Color.RED)

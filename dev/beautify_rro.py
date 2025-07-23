#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from argparse import ArgumentParser

from bp.bp_utils import ANDROID_BP_NAME
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
        process_rro(dir_path, dir_path)

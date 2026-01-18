#!/usr/bin/env python3
# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0


from argparse import ArgumentParser
from pathlib import Path

from rro.target_package import append_extra_locations, write_package_map


def generate_package_map():
    parser = ArgumentParser(
        prog='generate_package_map',
        description='Generate a cache for the package map',
    )
    parser.add_argument(
        'output_path',
        type=Path,
    )
    parser.add_argument(
        'extra_package_locations',
        nargs='*',
    )
    args = parser.parse_args()

    append_extra_locations(args.extra_package_locations)

    write_package_map(args.output_path)


if __name__ == '__main__':
    generate_package_map()

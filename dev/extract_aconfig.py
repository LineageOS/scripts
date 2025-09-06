#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
import subprocess
from argparse import ArgumentParser
from glob import glob
from pathlib import Path
from typing import Dict

from bp.bp_utils import ANDROID_BP_COPYRIGHT
from utils.utils import Color, android_root, color_print

aconfig_protos = Path(
    android_root,
    'build/make/tools/aconfig/aconfig_protos/protos',
)

dir_path = os.path.dirname(os.path.realpath(__file__))

for name in glob(f'{aconfig_protos}/*.proto'):
    subprocess.run(
        [
            'protoc',
            '--proto_path=.',
            f'--python_out={dir_path}',
            os.path.basename(name),
        ],
        cwd=aconfig_protos,
    )


from aconfig_pb2 import parsed_flags, parsed_flag, flag_state, flag_permission


def flag_file_name(flag: parsed_flag):
    source = flag.trace[-1].source
    return Path(source).name


def extract_aconfig():
    parser = ArgumentParser(
        prog='extract_aconfig',
        description='Extract aconfigs',
    )
    parser.add_argument(
        '-s',
        '--set-name',
        action='store',
        required=True,
        help='Name for the aconfig_value_set (eg: lineage-bp2a)',
    )
    parser.add_argument(
        '-v',
        '--values-prefix',
        action='store',
        required=True,
        help='Prefix to use for the aconfig_values name (eg: bp2a)',
    )
    parser.add_argument('aconfig_flags_pb')
    parser.add_argument('output_dir')

    aconfig_storage_rel_path = 'out/host/linux-x86/bin/aconfig-storage'
    aconfig_storage_path = Path(android_root, aconfig_storage_rel_path)
    if not aconfig_storage_path.exists():
        color_print(
            f'{aconfig_storage_rel_path} does not exist, run "m aconfig-storage"',
            color=Color.RED,
        )
        exit(-1)

    args = parser.parse_args()
    output_dir: str = args.output_dir
    values_prefix: str = args.values_prefix
    set_name: str = args.set_name

    def aconfig_values_name_for_package(package_name: str):
        return f'aconfig-values-{values_prefix}-{package_name}-all'

    parsed_flags_list = parsed_flags()
    with open(args.aconfig_flags_pb, 'rb') as pb:
        parsed_flags_list.ParseFromString(pb.read())

    package_flags_map: Dict[str, parsed_flag] = {}
    for flag in parsed_flags_list.parsed_flag:
        package_flags_map.setdefault(flag.package, []).append(flag)

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    android_bp = Path(output_dir, 'Android.bp')
    with open(android_bp, 'w') as o:
        o.write(f"""{ANDROID_BP_COPYRIGHT}
aconfig_value_set {{
  name: "aconfig_value_set-{set_name}",
  values: [
""")
        for package_name in package_flags_map.keys():
            values_name = aconfig_values_name_for_package(package_name)
            o.write(f'    "{values_name}",\n')

        o.write(
            """  ],
}
"""
        )

    for package_name, flags in package_flags_map.items():
        values_name = aconfig_values_name_for_package(package_name)

        package_dir = Path(output_dir, package_name)
        Path.mkdir(package_dir, parents=True, exist_ok=True)

        package_android_bp = Path(package_dir, 'Android.bp')
        with open(package_android_bp, 'w') as o:
            o.write(
                f'''{ANDROID_BP_COPYRIGHT}
aconfig_values {{
  name: "{values_name}",
  package: "{package_name}",
  srcs: [
    "*.textproto",
  ]
}}
'''
            )

        flags_map: Dict[str, parsed_flag] = {}
        for flag in flags:
            file_name = flag_file_name(flag)
            flags_map.setdefault(file_name, []).append(flag)

        for file_name, flags in flags_map.items():
            file_path = Path(package_dir, file_name)

            with open(file_path, 'w') as o:
                first = True
                for flag in flags:
                    if not first:
                        o.write('\n')
                    first = False

                    o.write(
                        f'''
flag_value {{
  package: "{package_name}"
  name: "{flag.name}"
  state: {flag_state.Name(flag.state)}
  permission: {flag_permission.Name(flag.permission)}
}}
'''.lstrip()
                    )


if __name__ == '__main__':
    extract_aconfig()

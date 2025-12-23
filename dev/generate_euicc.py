#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import textwrap
from os import path
from tempfile import TemporaryDirectory

from rro.manifest import ANDROID_MANIFEST_NAME, write_manifest
from rro.process_rro import write_rro_android_bp
from utils.utils import Color, color_print, run_cmd
from utils.xml_utils import XML_COMMENT_TEXT

TARGET_PACKAGE = 'org.lineageos.euicc'
TARGET_PACKAGE_STRINGS = {
    'carrier_list_json',
    'transfer_carrier_list_json',
    'sim_illustration_lottie_mappings_json',
    'sim_intro_illustration_lottie_mappings_json',
    'sim_intro_image_mappings_json',
    'sim_slot_mappings_json',
}
TARGET_PACKAGE_STRINGS_HELP = ', '.join(sorted(TARGET_PACKAGE_STRINGS))

def die(msg: str, code: int = 1) -> None:
    color_print(f'error: {msg}', color=Color.RED)
    raise SystemExit(code)


def extract_from_apk(
    vendor: str,
    apk_path: str,
    overlays_path: str,
    replacements: dict[str, str],
    ignore: set[str],
) -> None:
    with TemporaryDirectory() as tmp_dir:
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

        apk_strings = path.join(
            tmp_dir,
            'res',
            'values',
            'strings.xml'
        )
        if not path.exists(apk_strings):
            die('strings.xml not found')

        with open(apk_strings, encoding='utf-8', errors='replace') as f:
            raw_xml = f.read()
        apk_data = {}

        for name in TARGET_PACKAGE_STRINGS - ignore:
            match = re.search(
                rf'<string[^>]*name="{name}"[^>]*>(.*?)</string>',
                raw_xml,
                re.DOTALL,
            )

            if not match:
                continue

            value = html.unescape(match.group(1).strip()).replace(r'\"', '"')
            apk_data[name] = json.loads(value) if value else {}

    vendor_name = vendor[:1].upper() + vendor[1:]
    module_name = f'EuiccPolicy{vendor_name}'
    outdir = path.join(overlays_path, module_name)
    values_dir = path.join(
        outdir,
        'res',
        'values'
    )

    existing_data = {}
    strings_xml = path.join(values_dir, 'strings.xml')

    if path.exists(strings_xml):
        with open(strings_xml, encoding='utf-8', errors='replace') as f:
            raw_xml = f.read()

        for name in TARGET_PACKAGE_STRINGS - ignore:
            match = re.search(
                rf'<string[^>]*name="{name}"[^>]*>(.*?)</string>',
                raw_xml,
                re.DOTALL,
            )

            if not match:
                continue

            value = html.unescape(match.group(1).strip()).replace(r'\"', '"')
            existing_data[name] = json.loads(value) if value else {}

    merged = dict(existing_data)

    for name, incoming in apk_data.items():
        current = merged.get(name, {})
        for k, v in incoming.items():
            if k not in current:
                current[k] = v
        merged[name] = current

    def group_device_mappings(blob: dict, list_key: str) -> dict:
        """
        Canonically group device mappings by identical configuration
        (all fields except 'devices'), merge devices, and emit in
        deterministic order.
        """
        entries = blob.get(list_key, [])
        grouped = {}

        for entry in entries:
            config = {k: v for k, v in entry.items() if k != 'devices'}
            devices = entry.get('devices', [])

            key = json.dumps(config, sort_keys=True)
            grouped.setdefault(key, {'config': config, 'devices': []})
            grouped[key]['devices'].extend(devices)

        return {
            list_key: [
                {
                    'devices': sorted(set(item['devices'])),
                    **item['config'],
                }
                for key, item in sorted(grouped.items(), key=lambda kv: kv[0])
            ]
        }

    if 'sim_slot_mappings_json' in merged:
        merged['sim_slot_mappings_json'] = group_device_mappings(
            merged['sim_slot_mappings_json'],
            'sim-slot-mappings',
        )

    if 'sim_illustration_lottie_mappings_json' in merged:
        blob = merged['sim_illustration_lottie_mappings_json']
        entries = blob.get('sim_illustration_lottie_mappings', [])

        for entry in entries:
            target = entry.get('illustration_lottie')
            if target in replacements:
                entry['illustration_lottie'] = replacements[target]

        merged['sim_illustration_lottie_mappings_json'] = group_device_mappings(
            blob,
            'sim_illustration_lottie_mappings',
        )

    shutil.rmtree(outdir, ignore_errors=True)
    os.makedirs(outdir, exist_ok=True)

    write_rro_android_bp(
        apk_path='',
        android_bp_path=path.join(outdir, 'Android.bp'),
        package=module_name,
        aapt_raw=False,
        partition='product',
    )

    write_manifest(
        path.join(outdir, ANDROID_MANIFEST_NAME),
        package=f'{TARGET_PACKAGE}.overlay.{vendor}',
        target_package=TARGET_PACKAGE,
        overlay_attrs={'isStatic': 'true'},
    )

    os.makedirs(values_dir, exist_ok=True)

    with open(strings_xml, 'w', encoding='utf-8') as f:
        f.write('<?xml version="1.0" encoding="utf-8"?>\n')
        f.write(f'<!--{XML_COMMENT_TEXT}-->\n')
        f.write('<resources>\n')

        for name, data in merged.items():
            f.write(f'    <string name="{name}" translatable="false">\n')
            json_str = json.dumps(data, indent=4).replace('"', r'\"')
            json_str = textwrap.indent(json_str, ' ' * 8)
            f.write(json_str + '\n')
            f.write('    </string>\n')

        f.write('</resources>')

    color_print(f'Generated overlay in: {outdir}', color=Color.GREEN)


def generate_euicc() -> None:
    parser = argparse.ArgumentParser(
        prog='generate_euicc',
        description='Generate RRO overlay from apk resources',
    )

    parser.add_argument('apk_path')
    parser.add_argument(
        '-v',
        '--vendor',
        default='example',
        help='Vendor name used for the generated RRO overlay',
    )
    parser.add_argument(
        '-o',
        '--overlays',
        default='./overlays',
        help='Output directory for generated overlays',
    )
    parser.add_argument(
        '-r',
        '--replace',
        action='append',
        default=[],
        metavar='old:new',
        help='Replace a mapping value before grouping (can be specified multiple times).\n'
             'Format: old:new',
    )
    parser.add_argument(
        '-i',
        '--ignore',
        action='append',
        default=[],
        metavar='name',
        help=(
            'Skip processing of a string resource by name '
            '(can be specified multiple times). '
            f'Valid values: {TARGET_PACKAGE_STRINGS_HELP}'
        ),
    )

    args = parser.parse_args()

    if not path.exists(args.apk_path):
        die(f'APK not found: {args.apk_path}')

    replacements = {}

    for item in args.replace:
        if ':' not in item:
            die(f'Invalid --replace value (expected old:new): {item}')
        old, new = item.split(':', 1)
        replacements[old] = new

    ignore = set(args.ignore)

    unknown = ignore - TARGET_PACKAGE_STRINGS
    if unknown:
        die(f'Unknown --ignore value(s): {sorted(unknown)}')

    extract_from_apk(
        args.vendor,
        args.apk_path,
        args.overlays,
        replacements,
        ignore,
    )

if __name__ == '__main__':
    generate_euicc()

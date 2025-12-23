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
from os import path
from tempfile import TemporaryDirectory

from rro.manifest import ANDROID_MANIFEST_NAME, write_manifest
from rro.process_rro import write_rro_android_bp
from utils.utils import Color, color_print, run_cmd
from utils.xml_utils import XML_COMMENT_TEXT

TARGET_PACKAGE = 'org.lineageos.euicc'


def die(msg: str, code: int = 1) -> None:
    color_print(f'error: {msg}', color=Color.RED)
    raise SystemExit(code)


def extract_from_apk(vendor: str, apk_path: str, overlays_path: str) -> None:
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

        for name in (
            'sim_slot_mappings_json',
            'sim_illustration_lottie_mappings_json',
        ):
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

        for name in (
            'sim_slot_mappings_json',
            'sim_illustration_lottie_mappings_json',
        ):
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
        f.write('<resources>\n\n')

        for name, data in merged.items():
            f.write(f'    <string name="{name}" translatable="false">\n')
            f.write(json.dumps(data, indent=4).replace('"', r'\"') + '\n')
            f.write('    </string>\n\n')

        f.write('</resources>\n')

    color_print(f'Generated overlay in: {outdir}', color=Color.GREEN)


def generate_euicc() -> None:
    parser = argparse.ArgumentParser(
        prog='generate_euicc',
        description='Generate RRO overlay from EuiccPartnerApp resources',
    )

    parser.add_argument('apk_path')
    parser.add_argument('-v', '--vendor', default='example')
    parser.add_argument('-o', '--overlays', default='./overlays')

    args = parser.parse_args()

    if not path.exists(args.apk_path):
        die(f'APK not found: {args.apk_path}')

    extract_from_apk(args.vendor, args.apk_path, args.overlays)


if __name__ == '__main__':
    generate_euicc()

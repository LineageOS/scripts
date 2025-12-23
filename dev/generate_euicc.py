#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from rro.manifest import ANDROID_MANIFEST_NAME, write_manifest
from rro.process_rro import write_rro_android_bp
from utils.utils import Color, color_print, run_cmd
from utils.xml_utils import XML_COMMENT_TEXT

TARGET_PACKAGE = 'org.lineageos.euicc'


def die(msg: str, code: int = 1) -> None:
    color_print(f'error: {msg}', color=Color.RED)
    raise SystemExit(code)


def extract_from_apk(vendor: str, apk_path: Path, overlays_path: Path) -> None:
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

        apk_strings = Path(tmp_dir) / 'res' / 'values' / 'strings.xml'
        if not apk_strings.exists():
            die('strings.xml not found')

        raw_xml = apk_strings.read_text(encoding='utf-8', errors='replace')
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
    outdir = overlays_path / module_name
    values_dir = outdir / 'res' / 'values'

    existing_data = {}
    strings_xml = values_dir / 'strings.xml'

    if strings_xml.exists():
        raw_xml = strings_xml.read_text(encoding='utf-8', errors='replace')

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
    outdir.mkdir(parents=True, exist_ok=True)

    write_rro_android_bp(
        apk_path='',
        android_bp_path=str(outdir / 'Android.bp'),
        package=module_name,
        aapt_raw=False,
        partition='product',
    )

    write_manifest(
        str(outdir / ANDROID_MANIFEST_NAME),
        package=f'{TARGET_PACKAGE}.overlay.{vendor}',
        target_package=TARGET_PACKAGE,
        overlay_attrs={'isStatic': 'true'},
    )

    values_dir.mkdir(parents=True, exist_ok=True)

    with open(values_dir / 'strings.xml', 'w', encoding='utf-8') as f:
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

    apk_path = Path(args.apk_path)
    if not apk_path.exists():
        die(f'APK not found: {apk_path}')

    extract_from_apk(args.vendor, apk_path, Path(args.overlays))


if __name__ == '__main__':
    generate_euicc()

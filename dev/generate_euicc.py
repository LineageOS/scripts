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
from collections import defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory

from rro.manifest import ANDROID_MANIFEST_NAME, write_manifest
from rro.process_rro import write_rro_android_bp
from utils.utils import run_cmd, Color, color_print

TARGET_PACKAGE = 'org.lineageos.euicc'

LINE_RE = re.compile(
    r'^(?P<device>[A-Za-z0-9_-]+)'
    r'\[(?P<esim>[0-9,]*)\]'
    r'\[(?P<psim>[0-9,]*)\]$'
)


def die(msg: str, code: int = 1) -> None:
    color_print(f'error: {msg}', color=Color.RED)
    raise SystemExit(code)


def extract_apk(apk_path: str, tmp_dir: str) -> None:
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


def pascal_case(s: str) -> str:
    return s[:1].upper() + s[1:]


def format_device_line(device: str, esim: list[int], psim: list[int]) -> str:
    esim_s = ','.join(str(x) for x in sorted(esim))
    psim_s = ','.join(str(x) for x in sorted(psim))
    return f'{device}[{esim_s}][{psim_s}]'


def _normalize_json_text(raw: str) -> str:
    s = (raw or '').strip()
    s = html.unescape(s)
    s = s.replace(r'\"', '"')
    return s


def process_list(path: str):
    devices = {}

    if not os.path.exists(path):
        return devices

    with open(path, 'r', encoding='utf-8') as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            m = LINE_RE.match(line)
            if not m:
                die(f'Invalid line in {path}:{lineno}: {line}')

            device = m.group('device')
            esim = [int(x) for x in m.group('esim').split(',') if x]
            psim = [int(x) for x in m.group('psim').split(',') if x]

            devices[device] = (esim, psim)

    return devices


def extract_from_strings(apk_path: Path):

    with TemporaryDirectory() as tmp_dir:
        extract_apk(apk_path, tmp_dir)
        strings_xml = Path(tmp_dir) / 'res' / 'values' / 'strings.xml'

        if not strings_xml.exists():
            die(f'strings.xml not found: {strings_xml}')

        raw_xml = strings_xml.read_text(encoding='utf-8', errors='replace')

        m = re.search(
            r'<string[^>]+name="sim_slot_mappings_json"[^>]*>(.*?)</string>',
            raw_xml,
            re.DOTALL,
        )

        if not m:
            die('sim_slot_mappings_json not found in strings.xml')

        normalized = _normalize_json_text(m.group(1))

        try:
            data = json.loads(normalized)
        except json.JSONDecodeError as e:
            snippet = normalized[:300].replace('\n', '\\n')
            die(f'Failed to parse sim_slot_mappings_json: {e}\nSnippet: {snippet}')

        devices = {}
        for block in data.get('sim-slot-mappings', []):
            esim = sorted(block.get('esim-slot-ids', []) or [])
            psim = sorted(block.get('psim-slot-ids', []) or [])
            for dev in block.get('devices', []) or []:
                devices[dev] = (esim, psim)
    return devices


def generate_list(apk_path: str, devices_path: str) -> None:
    if not os.path.exists(apk_path):
        die(f'APK not found: {apk_path}')

    extracted = extract_from_strings(apk_path)
    existing = process_list(devices_path)
    merged = dict(existing)

    for dev, val in extracted.items():
        merged.setdefault(dev, val)

    with open(devices_path, 'w', encoding='utf-8') as f:
        f.write('# Automatically generated file. DO NOT MODIFY\n\n')
        for dev in sorted(merged):
            esim, psim = merged[dev]
            f.write(format_device_line(dev, esim, psim) + '\n')

    color_print(f'Updated {devices_path}', color=Color.GREEN)


def generate_resources(values_dir: Path, devices) -> None:
    groups = defaultdict(list)
    for dev, (esim, psim) in devices.items():
        groups[(tuple(sorted(esim)), tuple(sorted(psim)))].append(dev)

    sim_slot_mappings = []
    for (esim, psim), devs in sorted(groups.items()):
        sim_slot_mappings.append({
            'devices': sorted(devs),
            'esim-slot-ids': list(esim),
            'psim-slot-ids': list(psim),
        })

    data = {'sim-slot-mappings': sim_slot_mappings}

    with open(values_dir / 'strings.xml', 'w', encoding='utf-8') as f:
        f.write('<?xml version="1.0" encoding="utf-8"?>\n')
        f.write('<resources>\n\n')
        f.write('    <string name="sim_slot_mappings_json" translatable="false">\n')
        f.write(json.dumps(data, indent=4).replace('"', r'\"') + '\n')
        f.write('    </string>\n\n')
        f.write('</resources>\n')


def generate_rro(vendor: str, devices_path: str, overlays_path: str) -> None:
    devices = process_list(devices_path)
    if not devices:
        die('No devices found')

    Vendor = pascal_case(vendor)
    module_name = f'EuiccPolicy{Vendor}'
    outdir = Path(overlays_path) / module_name

    shutil.rmtree(outdir, ignore_errors=True)
    outdir.mkdir(parents=True, exist_ok=True)

    # Android.bp (shared RRO writer, no aapt raw)
    write_rro_android_bp(
        apk_path='',
        android_bp_path=str(outdir / 'Android.bp'),
        package=module_name,
        aapt_raw=False,
        partition='product',
    )

    # AndroidManifest.xml
    write_manifest(
        str(outdir / ANDROID_MANIFEST_NAME),
        package=f'{TARGET_PACKAGE}.overlay.{vendor}',
        target_package=TARGET_PACKAGE,
        overlay_attrs={'isStatic': 'true'},
    )

    # res/values
    values_dir = outdir / 'res' / 'values'
    values_dir.mkdir(parents=True, exist_ok=True)

    generate_resources(values_dir, devices)

    color_print(f'Generated overlay in: {outdir}', color=Color.GREEN)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        prog='generate_euicc',
        description='Update supported-devices.txt and generate EUICC overlays',
    )

    parser.add_argument('apk_path', nargs='?')

    parser.add_argument(
        '-d',
        '--devices',
        default='euicc-devices.txt',
        help='Supported device list',
    )

    parser.add_argument(
        '-v',
        '--vendor',
        default='example',
        help='Vendor name (Lowercase)',
    )

    parser.add_argument(
        '-o',
        '--overlays',
        default='./overlays',
        help='Output overlays directory',
    )

    args = parser.parse_args()

    if args.apk_path:
        generate_list(args.apk_path, args.devices)

    if args.vendor:
        generate_rro(args.vendor, args.devices, args.overlays)


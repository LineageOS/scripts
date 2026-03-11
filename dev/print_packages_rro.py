#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from argparse import ArgumentParser
from collections import defaultdict
from itertools import chain
from pathlib import Path
from typing import DefaultDict, List, Set

from bp.bp_utils import ANDROID_BP_NAME
from rro.overlay import Overlay, parse_overlay_from_android_bp
from utils.utils import get_dirs_with_file


def print_packages_rro():
    parser = ArgumentParser(
        prog='print_packages_rro',
        description='Print PRODUCT_PACKAGES for RROs',
    )

    parser.add_argument(
        'overlays',
        nargs='+',
        help='Overlays directory',
        type=Path,
    )

    args = parser.parse_args()

    device_devices_map: DefaultDict[str, Set[str]] = defaultdict(set)
    overlays: List[Overlay] = []

    for overlay_dir in chain.from_iterable(
        get_dirs_with_file(c, ANDROID_BP_NAME) for c in args.overlays
    ):
        overlay = parse_overlay_from_android_bp(
            Path(overlay_dir),
            read_meta=True,
        )

        if overlay is None:
            continue

        overlays.append(overlay)

        assert overlay.meta.device is not None
        assert overlay.meta.devices is not None
        device_devices_map[overlay.meta.device].update(overlay.meta.devices)

    device_overlays_map: DefaultDict[str, Set[str]] = defaultdict(set)
    for overlay in overlays:
        assert overlay.meta.devices is not None
        assert overlay.meta.device is not None

        if device_devices_map[overlay.meta.device] == overlay.meta.devices:
            device_overlays_map[overlay.meta.device].add(overlay.name)
            continue

        for device in overlay.meta.devices:
            device_overlays_map[device].add(overlay.name)

    for device, overlay_names in sorted(
        device_overlays_map.items(), key=lambda d: d[0]
    ):
        text = f'{device}:\n'
        text += 'PRODUCT_PACKAGES += \\\n'
        last = len(overlay_names) - 1
        for i, overlay_name in enumerate(sorted(overlay_names)):
            text += f'    {overlay_name}'
            if i != last:
                text += ' \\'
            text += '\n'
        print(text)


if __name__ == '__main__':
    print_packages_rro()

#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import shutil
from argparse import ArgumentParser
from pathlib import Path
from typing import Dict, List, Set, Tuple

from bp.bp_utils import ANDROID_BP_NAME
from rro.overlay import (
    Overlay,
    parse_overlay_from_android_bp,
    simplify_overlay_name_and_package,
    write_overlay,
)
from rro.resources import (
    keep_referenced_resources_from_removal,
)
from utils.utils import get_dirs_with_file


def commonize_package_overlays(
    overlays: List[Overlay],
    device: str,
    output_path: Path,
    verbose: bool,
):
    common_overlay_resources = None
    devices: Set[str] = set()
    for overlay in overlays:
        if overlay.meta.devices is None:
            raise ValueError('Generation was done without --device argument')

        devices.update(overlay.meta.devices)

        if common_overlay_resources is None:
            common_overlay_resources = overlay.resources.all().copy()
        else:
            common_overlay_resources &= overlay.resources.all()

    assert common_overlay_resources is not None

    if not common_overlay_resources:
        return

    for overlay in overlays:
        keep_referenced_resources_from_removal(
            resources_to_remove=common_overlay_resources,
            all_resources=overlay.resources,
            package=overlay.package,
            verbose=verbose,
        )

    overlay = None
    add_device_suffix = False
    for overlay in overlays:
        overlay.resources.remove_many(common_overlay_resources)

        shutil.rmtree(overlay.path)

        # Add device suffix if there are resources left or if it was already
        # added previously
        if overlay.resources or overlay.meta.has_device_suffix:
            add_device_suffix = True

    for overlay in overlays:
        if not overlay.resources:
            continue

        simplify_overlay_name_and_package(
            overlay,
            add_device_suffix=add_device_suffix,
        )

        overlay.path.mkdir(parents=True, exist_ok=True)

        write_overlay(
            overlay,
            # Write meta to allow commonize script to generate its own names
            write_meta=True,
        )

    assert overlay is not None

    overlay.meta.device = device
    overlay.path = Path(output_path, overlay.path.name)
    simplify_overlay_name_and_package(
        overlay,
        add_device_suffix=add_device_suffix,
    )

    overlay.meta.devices = devices
    overlay.resources.clear()
    overlay.resources.add_many(common_overlay_resources)

    write_overlay(
        overlay,
        # Write meta for further commonize
        write_meta=True,
    )


def commonize_overlays():
    parser = ArgumentParser(
        prog='commonize_rro',
        description='Commonize RROs',
    )

    parser.add_argument(
        'overlays',
        nargs='+',
        help='Overlays directory',
        type=Path,
    )
    parser.add_argument(
        '-o',
        '--output',
        help='Output directory for the common overlays',
        type=Path,
    )
    parser.add_argument(
        '-d',
        '--device',
        help='Device name to be used for the common RROs',
        required=True,
    )
    parser.add_argument(
        '-v',
        '--verbose',
        help='Print verbose output',
        action='store_true',
    )

    args = parser.parse_args()

    assert isinstance(args.output, Path)
    args.output.mkdir(parents=True, exist_ok=True)

    overlays_map: Dict[
        Tuple[
            # package name
            str,
            # overlay attributes
            Tuple[Tuple[str, str], ...],
        ],
        List[Overlay],
    ] = {}
    for overlays_path in args.overlays:
        assert isinstance(overlays_path, Path)

        for overlay_dir in get_dirs_with_file(
            str(overlays_path),
            ANDROID_BP_NAME,
        ):
            overlay_path = Path(overlay_dir)

            overlay = parse_overlay_from_android_bp(
                overlay_path,
                # Keep indices since we do not fixup in commonize
                track_index=True,
                # Read meta left over by generate script
                read_meta=True,
            )
            if overlay is None:
                continue

            overlays = overlays_map.setdefault(
                (
                    overlay.meta.original_package,
                    overlay.attrs_key(with_priority=True),
                ),
                [],
            )

            overlays.append(overlay)

    for overlays in overlays_map.values():
        if len(overlays) == 1:
            continue

        commonize_package_overlays(
            overlays,
            args.device,
            args.output,
            verbose=args.verbose,
        )


if __name__ == '__main__':
    commonize_overlays()

#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import shutil
from argparse import ArgumentParser
from pathlib import Path
from typing import Dict, List, Tuple

from bp.bp_utils import ANDROID_BP_NAME
from rro.manifest import ANDROID_MANIFEST_NAME
from rro.overlay import (
    Overlay,
    parse_overlay_from_android_bp,
    simplify_overlay_name,
    simplify_overlay_package,
    write_overlay,
)
from rro.resource_map import IndexFlags
from rro.resources import (
    RESOURCES_DIR,
    ResourceMap,
    keep_referenced_resources_from_removal,
)
from utils.utils import get_dirs_with_file


def commonize_package_overlays(
    overlays: List[Overlay],
    device: str,
    output_path: Path,
):
    common_overlay_resources = None
    for overlay in overlays:
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
        )

    overlay = None
    for overlay in overlays:
        overlay.resources.remove_many(common_overlay_resources)

        shutil.rmtree(overlay.path)

        if not overlay.resources:
            continue

        overlay.path.mkdir(parents=True, exist_ok=True)

        write_overlay(
            overlay,
            # Write meta to allow commonize script to generate its own names
            write_meta=True,
        )

    assert overlay is not None

    assert overlay.original_name is not None
    name, original_name = simplify_overlay_name(
        overlay.original_name,
        device,
        overlay.device,
    )

    assert overlay.original_package is not None
    package, original_package = simplify_overlay_package(
        overlay.original_package,
        device,
        overlay.device,
    )

    overlay_output_path = Path(output_path, name)
    shutil.rmtree(overlay_output_path, ignore_errors=True)
    overlay_output_path.mkdir(parents=True, exist_ok=True)

    common_overlay = Overlay(
        name=name,
        path=overlay_output_path,
        manifest_name=ANDROID_MANIFEST_NAME,
        resources_dir=RESOURCES_DIR,
        partition=overlay.partition,
        package=package,
        target_package=overlay.target_package,
        attrs=overlay.attrs,
        resources=ResourceMap(
            common_overlay_resources,
            indices=IndexFlags.BY_REL_PATH,
        ),
        original_name=original_name,
        original_package=original_package,
        original_target_package=overlay.target_package,
        device=device,
    )

    write_overlay(
        common_overlay,
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

            assert overlay.original_package is not None

            overlays = overlays_map.setdefault(
                (
                    overlay.original_package,
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
        )


if __name__ == '__main__':
    commonize_overlays()

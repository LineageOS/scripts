#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import shutil
from argparse import ArgumentParser
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set, Tuple

from bp.bp_module import parse_bp_rro_module
from bp.bp_utils import ANDROID_BP_NAME, get_module_partition
from rro.manifest import ANDROID_MANIFEST_NAME, parse_overlay_manifest
from rro.process_rro import (
    overlay_attrs_key,
    read_rro_meta,
    simplify_rro_name,
    simplify_rro_package,
    write_rro,
    write_rro_meta,
)
from rro.resources import (
    RESOURCES_DIR,
    Resource,
    parse_overlay_resources,
    remove_resources_referenced,
)
from rro.target_package import fixup_target_package
from utils.utils import Color, color_print, get_dirs_with_file


@dataclass
class OverlayData:
    path: Path
    name: str
    package: str
    target_package: str
    partition: str
    attrs: Dict[str, str]
    resources: Set[Resource]


def commonize_package_overlays(
    common_package: str,
    overlays_data: List[OverlayData],
    device: str,
    output_path: Path,
):
    print(f'{common_package}: commonizing')

    common_overlay_resources = None
    common_overlays_data: List[OverlayData] = []
    for overlay_data in overlays_data:
        if common_overlay_resources is None:
            common_overlay_resources = overlay_data.resources.copy()
        else:
            common_overlay_resources &= overlay_data.resources

        color_print(
            f'{common_package}: {overlay_data.path} has '
            f'{len(overlay_data.resources)} resources',
            color=Color.GREEN,
        )

        common_overlays_data.append(overlay_data)

    assert common_overlay_resources is not None

    if not common_overlay_resources:
        color_print(
            f'{common_package}: has no common resources',
            color=Color.YELLOW,
        )
        return

    for overlay_data in overlays_data:
        common_overlay_resources &= remove_resources_referenced(
            common_overlay_resources,
            overlay_data.resources - common_overlay_resources,
        )

    color_print(
        f'{common_package}: has '
        f'{len(common_overlay_resources)} common resources',
        color=Color.GREEN,
    )

    rro_meta = None
    overlay_data = None
    for overlay_data in common_overlays_data:
        overlay_data.resources -= common_overlay_resources

        color_print(
            f'{common_package}: {overlay_data.path} has '
            f'{len(overlay_data.resources)} resources left',
            color=Color.GREEN,
        )

        rro_meta = read_rro_meta(overlay_data.path)

        shutil.rmtree(overlay_data.path)

        if not overlay_data.resources:
            continue

        overlay_data.path.mkdir(parents=True, exist_ok=True)

        write_rro(
            overlay_data.resources,
            str(overlay_data.path),
            overlay_data.name,
            overlay_data.package,
            overlay_data.target_package,
            overlay_data.attrs,
            partition=overlay_data.partition,
        )
        write_rro_meta(
            overlay_data.path,
            rro_meta['original_rro_name'],
            rro_meta['original_package'],
            rro_meta['original_target_package'],
            device=rro_meta.get('device'),
        )

    assert rro_meta is not None
    assert overlay_data is not None

    reference_device = rro_meta.get('device')

    package = rro_meta['original_package']
    package, original_package = simplify_rro_package(
        package,
        device,
        reference_device,
    )

    target_package = rro_meta['original_target_package']
    target_package, orignal_target_package = fixup_target_package(
        target_package,
    )

    rro_name = rro_meta['original_rro_name']
    rro_name, original_rro_name = simplify_rro_name(
        rro_name,
        device,
        reference_device,
    )

    overlay_output_path = Path(output_path, rro_name)
    overlay_output_path.mkdir(parents=True, exist_ok=True)

    write_rro(
        common_overlay_resources,
        str(overlay_output_path),
        rro_name,
        package,
        target_package,
        overlay_data.attrs,
        partition=overlay_data.partition,
    )
    write_rro_meta(
        overlay_output_path,
        original_rro_name,
        original_package,
        orignal_target_package,
        device,
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
        List[OverlayData],
    ] = {}
    for overlays_path in args.overlays:
        assert isinstance(overlays_path, Path)

        for overlay_dir in get_dirs_with_file(
            str(overlays_path),
            ANDROID_BP_NAME,
        ):
            overlay_path = Path(overlay_dir)

            android_bp_path = Path(overlay_path, ANDROID_BP_NAME)
            statement = parse_bp_rro_module(android_bp_path)

            module_name = statement['name']
            module_partition = get_module_partition(statement)

            manifest = statement.get('manifest', ANDROID_MANIFEST_NAME)
            manifest_path = Path(overlay_path, manifest)

            resources_dir = statement.get('resource_dirs', [RESOURCES_DIR])[0]
            resources_path = Path(overlay_path, resources_dir)

            package, target_package, overlay_attrs = parse_overlay_manifest(
                str(manifest_path),
            )

            rro_meta = read_rro_meta(overlay_path)
            original_package = rro_meta['original_package']

            overlays_data = overlays_map.setdefault(
                (
                    original_package,
                    overlay_attrs_key(
                        overlay_attrs,
                        with_priority=True,
                    ),
                ),
                [],
            )

            overlay_resources = parse_overlay_resources(str(resources_path))
            overlay_data = OverlayData(
                path=overlay_path,
                name=module_name,
                package=package,
                target_package=target_package,
                partition=module_partition,
                attrs=overlay_attrs,
                resources=overlay_resources,
            )
            overlays_data.append(overlay_data)

    for (package, _), overlays_data in overlays_map.items():
        if len(overlays_data) == 1:
            continue

        commonize_package_overlays(
            package,
            overlays_data,
            args.device,
            args.output,
        )


if __name__ == '__main__':
    commonize_overlays()

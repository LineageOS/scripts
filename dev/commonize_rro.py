#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import shutil
from argparse import ArgumentParser
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set, cast

from bp.bp_module import BpModule
from bp.bp_parser import bp_parser  # type: ignore
from bp.bp_utils import ANDROID_BP_NAME, get_module_partition
from rro.manifest import ANDROID_MANIFEST_NAME, parse_overlay_manifest
from rro.process_rro import (
    parse_rro,
    read_rro_meta,
    simplify_rro_name,
    simplify_rro_package,
    write_rro,
    write_rro_meta,
)
from rro.resources import Resource
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
    overlay_paths: List[Path],
    device: str,
    output_path: Path,
):
    overlays_data: List[OverlayData] = []

    print(f'{common_package}: commonizing')

    common_overlay_resources = None
    for overlay_path in overlay_paths:
        print(f'{common_package}: parsing {overlay_path}')

        android_bp_path = Path(overlay_path, ANDROID_BP_NAME)
        statements = bp_parser.parse(android_bp_path.read_text())  # type: ignore
        statements = cast(List[BpModule], statements)
        assert len(statements) == 1

        statement = statements[0]
        module_name = statement['name']
        module_partition = get_module_partition(statement)

        manifest_path = Path(overlay_path, ANDROID_MANIFEST_NAME)
        package, target_package, overlay_attrs = parse_overlay_manifest(
            str(manifest_path),
        )

        overlay_resources = parse_rro(
            str(overlay_path),
            package,
            target_package,
        )

        if common_overlay_resources is None:
            common_overlay_resources = overlay_resources.copy()
        else:
            common_overlay_resources &= overlay_resources

        overlay_data = OverlayData(
            path=overlay_path,
            name=module_name,
            package=package,
            target_package=target_package,
            partition=module_partition,
            attrs=overlay_attrs,
            resources=overlay_resources,
        )

        color_print(
            f'{common_package}: {overlay_data.path} has '
            f'{len(overlay_data.resources)} resources',
            color=Color.GREEN,
        )

        overlays_data.append(overlay_data)

    assert common_overlay_resources is not None

    if not common_overlay_resources:
        color_print(
            f'{common_package}: has no common resources',
            color=Color.YELLOW,
        )
        return

    color_print(
        f'{common_package}: has '
        f'{len(common_overlay_resources)} common resources',
        color=Color.GREEN,
    )

    rro_meta = None
    overlay_data = None
    for overlay_data in overlays_data:
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

    package = rro_meta['original_package']
    package, original_package = simplify_rro_package(package, device)

    target_package = rro_meta['original_target_package']
    target_package, orignal_target_package = fixup_target_package(
        target_package,
    )

    rro_name = rro_meta['original_rro_name']
    rro_name, original_rro_name = simplify_rro_name(rro_name, device)

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

    overlays_map: Dict[str, List[Path]] = {}
    for overlays_path in args.overlays:
        assert isinstance(overlays_path, Path)

        for dir_path in get_dirs_with_file(str(overlays_path), ANDROID_BP_NAME):
            dir_path = Path(dir_path)
            rro_meta = read_rro_meta(dir_path)
            package = rro_meta['original_package']
            overlay_paths = overlays_map.setdefault(package, [])
            overlay_paths.append(dir_path)

    for package, overlay_paths in overlays_map.items():
        if len(overlay_paths) == 1:
            continue

        commonize_package_overlays(
            package,
            overlay_paths,
            args.device,
            args.output,
        )


if __name__ == '__main__':
    commonize_overlays()

# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path
from typing import List, NotRequired, TypedDict, cast

from bp.bp_parser import bp_parser  # type: ignore


class BpModule(TypedDict):
    name: str
    module: str


class SoongConfigModuleTypeModule(BpModule):
    module_type: str


class FilegroupModule(BpModule):
    srcs: List[str]


class AppModule(BpModule):
    manifest: NotRequired[str]
    additional_manifests: NotRequired[List[str]]
    defaults: NotRequired[List[str]]
    static_libs: NotRequired[List[str]]
    resource_dirs: NotRequired[List[str]]


class RROModule(BpModule):
    manifest: NotRequired[str]
    resource_dirs: NotRequired[List[str]]


def parse_bp_rro_module(android_bp_path: Path):
    statements = bp_parser.parse(android_bp_path.read_text())  # type: ignore
    statements = cast(List[BpModule], statements)

    statements = list(
        filter(
            lambda s: s['module'] == 'runtime_resource_overlay',
            statements,
        )
    )

    assert len(statements) == 1, android_bp_path

    return cast(RROModule, statements[0])

# SPDX-FileCopyrightText: 2026 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

import re
import shutil
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from apk.arsc_parse import arsc_parse, get_resources_referenced_names
from apk.arsc_resources import ARSCResourcesMap
from apk.arsc_write import write_resources, write_resources_public_xml
from apk.axml_parse import AXMLParseError, axml_parse
from apk.axml_writer import AXMLWriter

ANDROID_MANIFEST_NAME = 'AndroidManifest.xml'
ANDROID_URI = 'http://schemas.android.com/apk/res/android'


def strip_version_qualifier(name: str) -> str:
    return re.sub(r'-v\d+$', '', name)


def normalize_mnc_qualifier(name: str) -> str:
    parts = name.split('-')

    for i, part in enumerate(parts):
        if not part.startswith('mnc'):
            continue

        digits = part[3:]
        if digits.isdigit() and len(digits) == 1:
            digits = f'0{digits}'

        parts[i] = 'mnc' + digits

    return '-'.join(parts)


def extract_apk_raw(
    z: zipfile.ZipFile,
    out_path: Path,
    strings: List[str],
    resources: ARSCResourcesMap,
    reference_resources: Optional[ARSCResourcesMap] = None,
    package_id_map: Optional[Dict[int, str]] = None,
):
    referenced_names = get_resources_referenced_names(
        resources,
        strings,
    )

    zip_file_paths = z.namelist()
    for zip_file_path in zip_file_paths:
        file_path = Path(out_path, zip_file_path)

        if (
            file_path.stem not in referenced_names
            and file_path.name != ANDROID_MANIFEST_NAME
        ):
            continue

        # TODO: remove apktool compatibility
        name = file_path.parent.name
        name = strip_version_qualifier(name)
        name = normalize_mnc_qualifier(name)
        file_path = Path(file_path.parent.parent, name, file_path.name)

        file_path.parent.mkdir(parents=True, exist_ok=True)

        data = z.read(zip_file_path)

        if not file_path.name.endswith('.xml'):
            file_path.write_bytes(data)
            continue

        # TODO: remove apktool compatibility
        is_manifest = file_path.name == ANDROID_MANIFEST_NAME
        skip_elements = None
        skip_attrs_by_elem: Optional[
            Dict[str, Set[Tuple[Optional[str], str]]]
        ] = None
        skip_space_before_close = False
        xmlns_first = False
        sort_attrs = False

        if is_manifest:
            skip_elements = {
                'uses-sdk',
            }
            skip_attrs_by_elem = {
                'manifest': {
                    (ANDROID_URI, 'versionCode'),
                    (ANDROID_URI, 'versionName'),
                }
            }
            skip_space_before_close = True
            xmlns_first = True
            sort_attrs = True

        try:
            with open(file_path, 'w') as o:
                writer = AXMLWriter(
                    o,
                    pretty=True,
                    skip_space_before_close=skip_space_before_close,
                    skip_elements=skip_elements,
                    skip_attrs_by_elem=skip_attrs_by_elem,
                    sort_attrs=sort_attrs,
                    xmlns_first=xmlns_first,
                )
                axml_parse(
                    data,
                    resources,
                    reference_resources,
                    package_id_map,
                    writer,
                )
        except AXMLParseError:
            file_path.write_bytes(data)


def extract_apk(
    apk_path: Path,
    out_path: Optional[Path] = None,
    reference_resources: Optional[ARSCResourcesMap] = None,
):
    with zipfile.ZipFile(apk_path, 'r') as z:
        assert 'resources.arsc' in z.namelist()

        arsc = z.read('resources.arsc')
        strings, styles, resources, flags, package_id_map = arsc_parse(arsc)

        if out_path is not None:
            extract_apk_raw(
                z,
                out_path,
                strings,
                resources,
                reference_resources,
                package_id_map,
            )

        return strings, styles, resources, flags, package_id_map


def extract_apks(
    apk_output_paths: List[Tuple[Path, Path]],
    framework_path: Path,
):
    assert isinstance(framework_path, Path)
    _, _, framework_resources, framework_flags, _ = extract_apk(framework_path)

    for apk_path, output_path in apk_output_paths:
        output_path.mkdir(parents=True, exist_ok=True)

        res_output_path = Path(output_path, 'res')
        shutil.rmtree(res_output_path, ignore_errors=True)
        res_output_path.mkdir(parents=True, exist_ok=True)

        strings, styles, resources, flags, package_id_map = extract_apk(
            apk_path,
            output_path,
            framework_resources,
        )
        assert strings is not None

        write_resources(
            strings,
            styles,
            package_id_map,
            resources,
            framework_resources,
            framework_flags,
            res_output_path,
        )
        write_resources_public_xml(
            resources,
            framework_resources,
            flags,
            res_output_path,
        )

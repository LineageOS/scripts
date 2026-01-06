# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Dict

from lxml import etree

from utils.xml_utils import XML_COMMENT

NAMESPACE_NAME = 'android'
NAMESPACE = 'http://schemas.android.com/apk/res/android'
ANDROID_MANIFEST_NAME = 'AndroidManifest.xml'
PACKAGE_KEY = 'package'
OVERLAY_TAG = 'overlay'
TARGET_PACKAGE_KEY = 'targetPackage'

OVERLAY_ATTRS = [
    'targetName',
    'isStatic',
    'priority',
    'requiredSystemPropertyName',
    'requiredSystemPropertyValue',
]


def namespace_attr(attr: str):
    return f'{{{NAMESPACE}}}{attr}'


def parse_package_manifest(manifest_path: str):
    tree = etree.parse(manifest_path)
    root = tree.getroot()

    return root.attrib.get(PACKAGE_KEY)


def parse_overlay_manifest(manifest_path: str):
    tree = etree.parse(manifest_path)
    root = tree.getroot()

    package = root.attrib.get(PACKAGE_KEY)
    assert package is not None

    overlay_elem = root.find(OVERLAY_TAG)
    assert overlay_elem is not None

    namespaced_attr = namespace_attr(TARGET_PACKAGE_KEY)
    target_package = overlay_elem.attrib.get(namespaced_attr)

    overlay_attrs: Dict[str, str] = {}

    for attr in OVERLAY_ATTRS:
        namespaced_attr = namespace_attr(attr)
        value = overlay_elem.attrib.get(namespaced_attr)
        if value is not None:
            overlay_attrs[attr] = value

    return package, target_package, overlay_attrs


def write_manifest(
    output_path: str,
    package: str,
    target_package: str,
    overlay_attrs: Dict[str, str],
):
    with open(output_path, 'w') as o:
        o.write('<?xml version="1.0" encoding="utf-8"?>')
        o.write(XML_COMMENT)

        o.write(f'<manifest xmlns:{NAMESPACE_NAME}="{NAMESPACE}"\n')
        o.write(f'          package="{package}">\n')
        o.write(
            f'    <overlay {NAMESPACE_NAME}:{TARGET_PACKAGE_KEY}="{target_package}"'
        )
        space = ''

        for attr, value in overlay_attrs.items():
            o.write(space)
            o.write(f'\n             {NAMESPACE_NAME}:{attr}="{value}"')

        o.write(' />\n')
        o.write('</manifest>\n')

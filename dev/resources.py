# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
from os import path
import shutil
from typing import Dict, List, Tuple

from lxml import etree

from manifest import NAMESPACE
from utils import (
    XML_COMMENT_TEXT,
    Color,
    color_print,
    xml_element_canonical_str,
)

TRANSLATABLE_KEY = 'translatable'
FEATURE_FLAG_KEY = 'featureFlag'
RESOURCES_TAG = 'resources'
RESOURCES_DIR = 'res'


class Resource:
    def __init__(
        self,
        index: int,
        rel_path: str,
        keys: Tuple[str],
        element: etree.Element,
        comment: etree._Comment,
    ):
        self.index = index
        self.rel_path = rel_path
        self.keys = keys
        self.element = element
        self.comment = comment

    @property
    def name(self):
        return self.element.attrib.get('name', '')


resources_dict = Dict[Tuple[str], Resource]
resources_grouped_dict = Dict[str, List[Resource]]


def parse_xml_resource(
    xml_rel_path: str,
    xml_path: str,
    resources: Dict[Tuple[str], Resource],
):
    tree = etree.parse(xml_path)
    root = tree.getroot()

    if root.tag != RESOURCES_TAG:
        return None

    etree.cleanup_namespaces(root)

    comment = None
    index = 0
    for node in root:
        if isinstance(node, etree._Comment):
            comment = node
            continue

        current_comment = comment
        comment = None

        if (
            node.tag == 'java-symbol'
            or node.tag == 'eat-comment'
            or node.tag == 'skip'
            or node.tag == 'public'
        ):
            continue

        name = node.attrib.get('name', '')
        if not name:
            continue

        product = node.attrib.get('product', '')
        feature_flag = node.attrib.get(f'{{{NAMESPACE}}}{FEATURE_FLAG_KEY}', '')
        keys = (node.tag, name, product, feature_flag)

        resource = Resource(index, xml_rel_path, keys, node, current_comment)
        index += 1

        if keys in resources:
            color_print(f'{xml_path}: {keys} already found', color=Color.YELLOW)
            continue

        resources[keys] = resource


def parse_package_resources_dir(
    package_dir: str,
    res_dir: str,
    resources: resources_dict,
):
    for dir_file in os.scandir(res_dir):
        if not dir_file.is_dir():
            continue

        if dir_file.name != 'values':
            continue

        for xml_file in os.scandir(dir_file.path):
            if not xml_file.is_file():
                continue

            if xml_file.name.startswith('public-'):
                continue

            if xml_file.name == 'symbols.xml':
                continue

            xml_rel_path = os.path.relpath(xml_file.path, package_dir)

            parse_xml_resource(xml_rel_path, xml_file.path, resources)

    return resources


def parse_overlay_resources(overlay_dir: str):
    resources: resources_dict = {}

    res_dir = path.join(overlay_dir, RESOURCES_DIR)
    if not path.exists(res_dir):
        return resources

    parse_package_resources_dir(
        overlay_dir,
        res_dir,
        resources,
    )

    return resources


def remove_overlay_resources(overlay_dir: str):
    res_dir = path.join(overlay_dir, RESOURCES_DIR)
    shutil.rmtree(res_dir, ignore_errors=True)


# TODO: cache
def parse_package_resources(package_dir: str, res_dirs: List[str]):
    resources: resources_dict = {}

    for res_dir in res_dirs:
        parse_package_resources_dir(
            package_dir,
            res_dir,
            resources,
        )

    return resources


def group_overlay_resources_rel_path(
    overlay_resources: resources_dict,
    package_resources: resources_dict,
):
    grouped_resources: resources_grouped_dict = {}
    missing_resources: List[Resource] = []
    identical_resources: List[Resource] = []

    for keys, resource in overlay_resources.items():
        package_resource = package_resources.get(keys)
        if package_resource is None:
            missing_resources.append(resource)
            continue

        # Overlays don't have translatable=false, remove it to fix
        # equality check
        if TRANSLATABLE_KEY in package_resource.element.attrib:
            del package_resource.element.attrib[TRANSLATABLE_KEY]

        if xml_element_canonical_str(
            package_resource.element
        ) == xml_element_canonical_str(resource.element):
            identical_resources.append(resource)
            continue

        # TODO: find out if this is needed
        # resource.element.attrib[TRANSLATABLE_KEY] = 'false'
        resource.index = package_resource.index
        resource.comment = package_resource.comment

        rel_path_resources = grouped_resources.setdefault(
            package_resource.rel_path,
            [],
        )
        rel_path_resources.append(resource)

    for _, resources in grouped_resources.items():
        resources.sort(key=lambda r: r.index)

    return grouped_resources, missing_resources, identical_resources


def write_xml_resources(xml_path: str, resources: List[Resource]):
    xml_dir_path = path.dirname(xml_path)
    os.makedirs(xml_dir_path, exist_ok=True)

    root = etree.Element(RESOURCES_TAG)
    tree = etree.ElementTree(root)

    copyright_comment = etree.Comment(XML_COMMENT_TEXT)
    root.addprevious(copyright_comment)

    next_line_spacing = '\n' + ' ' * 4
    root.text = next_line_spacing
    for resource in resources:
        if resource.comment is not None:
            resource.comment.tail = next_line_spacing
            root.append(resource.comment)

        resource.element.tail = '\n'
        if resource is not resources[-1]:
            resource.element.tail += next_line_spacing

        root.append(resource.element)

    text = etree.tostring(
        tree,
        pretty_print=True,
        # xml_declaration=True,
        encoding='utf-8',
    )
    with open(xml_path, 'wb') as o:
        # XML declaration uses single quotes in lxml
        # hardcode it
        o.write(b'<?xml version="1.0" encoding="utf-8"?>\n')
        o.write(text)


def write_grouped_resources(
    grouped_resources: resources_grouped_dict,
    output_path: str,
):
    for rel_path, resources in grouped_resources.items():
        xml_path = path.join(output_path, rel_path)
        write_xml_resources(xml_path, resources)

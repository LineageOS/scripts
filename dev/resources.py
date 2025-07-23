# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import functools
import os
import shutil
from os import path
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

        if (
            node.tag == 'java-symbol'
            or node.tag == 'eat-comment'
            or node.tag == 'skip'
            or node.tag == 'public'
        ):
            comment = None
            continue

        name = node.attrib.get('name', '')
        if not name:
            raise ValueError('Node has no name')

        # Assign the same comment to entries following each other without a
        # newline
        if node.tail is not None and node.tail.count('\n') != 1:
            comment = None

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
    xmls: Dict[str, str],
):
    for dir_file in os.scandir(res_dir):
        if not dir_file.is_dir():
            continue

        is_xml_dir = dir_file.name == 'xml'
        if dir_file.name != 'values' and not is_xml_dir:
            continue

        for xml_file in os.scandir(dir_file.path):
            if not xml_file.is_file():
                continue

            if xml_file.name.startswith('public-'):
                continue

            if xml_file.name == 'symbols.xml':
                continue

            xml_rel_path = os.path.relpath(xml_file.path, package_dir)

            if is_xml_dir:
                assert xml_file.name not in xmls
                xmls[xml_file.name] = xml_rel_path
                continue

            parse_xml_resource(xml_rel_path, xml_file.path, resources)


def parse_overlay_resources(overlay_dir: str):
    resources: resources_dict = {}
    xmls: Dict[str, str] = {}

    res_dir = path.join(overlay_dir, RESOURCES_DIR)
    if not path.exists(res_dir):
        return resources, xmls

    parse_package_resources_dir(
        overlay_dir,
        res_dir,
        resources,
        xmls,
    )

    return resources, xmls


def remove_overlay_resources(overlay_dir: str):
    res_dir = path.join(overlay_dir, RESOURCES_DIR)
    shutil.rmtree(res_dir, ignore_errors=True)


@functools.cache
def get_target_package_resources(package_dir: str, res_dirs: Tuple[str]):
    resources: resources_dict = {}
    xmls: Dict[str, str] = {}

    for res_dir in res_dirs:
        parse_package_resources_dir(
            package_dir,
            res_dir,
            resources,
            xmls,
        )

    return resources, xmls


def find_target_package_resources(
    target_packages: List[Tuple[str, Tuple[str]]],
    overlay_resources: resources_dict,
    overlay_xmls: Dict[str, str],
):
    max_matching_resources = 0
    best_resources = None

    for package_dir, resource_dirs in target_packages:
        resources = get_target_package_resources(package_dir, resource_dirs)
        package_resources, package_xmls = resources

        matching_resources = 0
        if len(target_packages) != 1:
            for keys in overlay_resources.keys():
                if keys in package_resources:
                    matching_resources += 1
            for xml_name in overlay_xmls:
                if xml_name in package_xmls:
                    matching_resources += 1

        if matching_resources >= max_matching_resources:
            best_resources = resources

    return best_resources


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
    last_element = None

    for resource in resources:
        # Add a newline and indent between this element and the last element
        if last_element is not None:
            last_element.tail = '\n' + next_line_spacing

        if resource.comment is not None:
            # Only add comment if its parent is not root
            # If parent is root then comment was added for past entries
            if resource.comment.getparent() != root:
                root.append(resource.comment)
                last_element = resource.comment

            last_element.tail = next_line_spacing

        root.append(resource.element)
        last_element = resource.element

    if last_element is not None:
        last_element.tail = '\n'

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


def read_overlay_xmls(
    overlay_path: str,
    overlay_xmls: Dict[str, str],
    package_xmls: Dict[str, str],
):
    missing_xmls: List[str] = []
    xmls: Dict[str, str] = {}

    for xml_name, overlay_xml_rel_path in overlay_xmls.items():
        if xml_name not in package_xmls:
            missing_xmls.append(xml_name)
            continue

        package_xml_rel_path = package_xmls[xml_name]
        xml_path = path.join(overlay_path, overlay_xml_rel_path)
        with open(xml_path, 'r') as xml:
            xmls[package_xml_rel_path] = xml.read()

    return xmls, missing_xmls


def write_overlay_xmls(xmls: Dict[str, str], output_path: str):
    for xml_rel_path, xml_data in xmls.items():
        xml_path = path.join(output_path, xml_rel_path)
        xml_dir_path = path.dirname(xml_path)
        os.makedirs(xml_dir_path, exist_ok=True)
        with open(xml_path, 'w') as xml:
            xml.write(xml_data)

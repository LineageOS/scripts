# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import functools
import os
import shutil
from os import path
from typing import Dict, List, Optional, Set, Tuple

from lxml import etree

from rro.manifest import NAMESPACE
from utils.utils import (
    Color,
    color_print,
)
from utils.xml_utils import XML_COMMENT_TEXT, xml_element_canonical_str

TRANSLATABLE_KEY = 'translatable'
FEATURE_FLAG_KEY = 'featureFlag'
RESOURCES_TAG = 'resources'
RESOURCES_DIR = 'res'


class Resource:
    def __init__(
        self,
        index: int,
        xml_name: str,
        rel_dir_path: str,
        keys: Tuple[str, ...],
        tag: str,
        name: str,
        element: etree.Element,
        comments: List[etree._Comment],
    ):
        self.index = index
        self.rel_path = None
        self.xml_name = xml_name
        self.rel_dir_path = rel_dir_path
        self.keys = keys
        self.tag = tag
        self.name = name
        self.element = element
        self.comments = comments
        self.references: List[Resource] = []


resources_dict = Dict[Tuple[str, ...], Resource]
resources_grouped_dict = Dict[str, List[Resource]]


def node_has_space_after(node: etree.Element):
    return node.tail is not None and node.tail.count('\n') > 1


def parse_xml_resource(
    xml_rel_path: str,
    xml_path: str,
    resources: Dict[Tuple[str, ...], Resource],
    is_default_values: bool,
):
    xml_rel_dir_path = path.dirname(xml_rel_path)
    xml_name = path.basename(xml_rel_path)

    tree = etree.parse(xml_path)
    root = tree.getroot()

    if root.tag != RESOURCES_TAG:
        return None

    etree.cleanup_namespaces(root)

    comments = []
    index = 0
    for node in root:
        if isinstance(node, etree._Comment):
            # Last element was not a comment, don't stack them
            # Or it was a comment, but they were not stacked
            last_node = node.getprevious()
            if not isinstance(
                last_node, etree._Comment
            ) or node_has_space_after(last_node):
                comments = []

            comments.append(node)
            continue

        tag = node.tag
        if (
            tag == 'java-symbol'
            or tag == 'eat-comment'
            or tag == 'skip'
            or tag == 'public'
        ):
            comments = []
            continue

        name = node.attrib.get('name', '')
        if not name:
            raise ValueError('Node has no name')

        product = node.attrib.get('product', '')
        # TODO: find out if this is really correct
        if product == 'default':
            product = ''

        feature_flag = node.attrib.get(f'{{{NAMESPACE}}}{FEATURE_FLAG_KEY}', '')

        if is_default_values:
            keys = ('', tag, name, product, feature_flag)
        else:
            keys = (xml_rel_path, tag, name, product, feature_flag)

        resource = Resource(
            index,
            xml_name,
            xml_rel_dir_path,
            keys,
            tag,
            name,
            node,
            comments,
        )
        index += 1

        # Assign the same comment to entries following each other without a
        # newline
        if node_has_space_after(node):
            comments = []

        if keys in resources:
            color_print(f'{xml_path}: {keys} already found', color=Color.YELLOW)
            continue

        resources[keys] = resource


def parse_package_resources_dir(
    res_dir: str,
    resources: resources_dict,
    xmls: Dict[str, str],
    parse_all_values: bool = False,
):
    for dir_file in os.scandir(res_dir):
        if not dir_file.is_dir():
            continue

        if dir_file.name.startswith(('values-en-rXA', 'values-ar-rXB')):
            continue

        is_xml_dir = dir_file.name == 'xml'
        is_default_values = dir_file.name == 'values'
        if parse_all_values:
            is_values = dir_file.name.startswith('values')
        else:
            is_values = is_default_values

        if not is_values and not is_xml_dir:
            continue

        for xml_file in os.scandir(dir_file.path):
            if not xml_file.is_file():
                continue

            if xml_file.name.startswith('public-'):
                continue

            if xml_file.name == 'symbols.xml':
                continue

            # Some apps don't place their res directory directly under
            # the package directory
            # Only keep the resource directory name
            xml_resources_dir_name = path.basename(res_dir)
            xml_file_path = path.relpath(xml_file.path, res_dir)
            xml_rel_path = path.join(xml_resources_dir_name, xml_file_path)

            if is_xml_dir:
                assert xml_file.name not in xmls
                xmls[xml_file.name] = xml_rel_path
                continue

            parse_xml_resource(
                xml_rel_path,
                xml_file.path,
                resources,
                is_default_values,
            )


def parse_overlay_resources(
    overlay_dir: str, resources_dir: str = RESOURCES_DIR
):
    resources: resources_dict = {}
    xmls: Dict[str, str] = {}

    res_dir = path.join(overlay_dir, resources_dir)
    if not path.exists(res_dir):
        return resources, xmls

    parse_package_resources_dir(
        res_dir,
        resources,
        xmls,
        parse_all_values=True,
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


def get_correct_resource_type(
    resource: Resource,
    package_resources: resources_dict,
):
    for package_resource in package_resources.values():
        if resource.name == package_resource.name:
            return package_resource.tag

    return None


def is_referenced_resource_element(
    reference_name: str,
    element: etree.Element,
):
    if element.text is not None and element.text.strip() == reference_name:
        return True

    for child_element in element:
        if is_referenced_resource_element(reference_name, child_element):
            return True

    return False


def get_referencing_resource(
    resource: Resource,
    overlay_resources: resources_dict,
):
    reference_name = f'@{resource.tag}/{resource.name}'
    for overlay_resource in overlay_resources.values():
        if is_referenced_resource_element(
            reference_name,
            overlay_resource.element,
        ):
            return overlay_resource

    return None


def group_overlay_resources_rel_path(
    overlay_resources: resources_dict,
    package_resources: resources_dict,
):
    grouped_resources: resources_grouped_dict = {}
    missing_resources: Set[str] = set()
    wrong_type_resources: Set[Tuple[str, str, str]] = set()
    identical_resources: Set[str] = set()

    for keys, resource in overlay_resources.items():
        package_resource = package_resources.get(keys)
        if package_resource is None:
            default_location_keys = ('', *keys[1:])
            package_resource = package_resources.get(default_location_keys)

        if package_resource is None:
            correct_resource_type = get_correct_resource_type(
                resource,
                package_resources,
            )
            if correct_resource_type is not None:
                wrong_type_resources.add(
                    (resource.name, resource.tag, correct_resource_type)
                )
                continue

            referencing_resource = get_referencing_resource(
                resource,
                overlay_resources,
            )
            if referencing_resource is not None:
                referencing_resource.references.append(resource)
                continue

            missing_resources.add(resource.name)
            continue

        # Overlays don't have translatable=false, remove it to fix
        # equality check
        if TRANSLATABLE_KEY in package_resource.element.attrib:
            del package_resource.element.attrib[TRANSLATABLE_KEY]

        if xml_element_canonical_str(
            package_resource.element
        ) == xml_element_canonical_str(resource.element):
            identical_resources.add(resource.name)
            continue

        # TODO: find out if this is needed
        # resource.element.attrib[TRANSLATABLE_KEY] = 'false'
        resource.index = package_resource.index
        resource.comments = package_resource.comments

        # Keep the directory of the original resource, but place it in the
        # correct XML
        rel_path = path.join(resource.rel_dir_path, package_resource.xml_name)
        grouped_resources.setdefault(rel_path, []).append(resource)

    for _, resources in grouped_resources.items():
        resources.sort(key=lambda r: r.index)

    return (
        grouped_resources,
        wrong_type_resources,
        missing_resources,
        identical_resources,
    )


def write_xml_resources(
    xml_path: str,
    resources: List[Resource],
    maintain_copyrights: bool = False,
    preserved_prefix: Optional[bytes] = None,
):
    xml_dir_path = path.dirname(xml_path)
    os.makedirs(xml_dir_path, exist_ok=True)

    root = etree.Element(RESOURCES_TAG)
    tree = etree.ElementTree(root)

    # Only add default header when we're NOT preserving an existing prefix
    if not (maintain_copyrights and preserved_prefix is not None):
        root.addprevious(etree.Comment(XML_COMMENT_TEXT))

    next_line_spacing = '\n' + ' ' * 4
    root.text = next_line_spacing
    last_element = None

    for resource in resources:
        # Add a newline and indent between this element and the last element
        if last_element is not None:
            last_element.tail = '\n' + next_line_spacing

        for comment in resource.comments:
            # Only add comment if its parent is not root
            # If parent is root then comment was added for past entries
            if comment.getparent() != root:
                root.append(comment)
                last_element = comment

            last_element.tail = next_line_spacing

        root.append(resource.element)
        last_element = resource.element

        for reference_resource in resource.references:
            root.append(reference_resource.element)

    if last_element is not None:
        last_element.tail = '\n'

    xml_body = etree.tostring(
        tree,
        pretty_print=True,
        encoding='utf-8',
    )

    with open(xml_path, 'wb') as o:
        if maintain_copyrights and preserved_prefix is not None:
            o.write(preserved_prefix)
        else:
            o.write(b'<?xml version="1.0" encoding="utf-8"?>\n')
        o.write(xml_body)


def write_grouped_resources(
    grouped_resources: resources_grouped_dict,
    output_path: str,
    maintain_copyrights: bool = False,
    preserved_prefixes: Optional[Dict[str, Optional[bytes]]] = None,
):
    for rel_path, resources in grouped_resources.items():
        xml_path = path.join(output_path, rel_path)
        preserved = None
        if maintain_copyrights and preserved_prefixes is not None:
            preserved = preserved_prefixes.get(xml_path)

        write_xml_resources(
            xml_path,
            resources,
            maintain_copyrights=maintain_copyrights,
            preserved_prefix=preserved,
        )


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
        with open(xml_path, 'rb') as xml:
            xmls[package_xml_rel_path] = xml.read()

    return xmls, missing_xmls


def write_overlay_xmls(xmls: Dict[str, str], output_path: str):
    for xml_rel_path, xml_data in xmls.items():
        xml_path = path.join(output_path, xml_rel_path)
        xml_dir_path = path.dirname(xml_path)
        os.makedirs(xml_dir_path, exist_ok=True)
        with open(xml_path, 'wb') as xml:
            xml.write(xml_data)

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
            # color_print(f'{xml_path}: {keys} already found', color=Color.YELLOW)
            continue

        resources[keys] = resource


def parse_package_resources_dir(
    res_dir: str,
    resources: resources_dict,
    raw_resources: Dict[str, str],
    parse_all_values: bool = False,
):
    for dir_file in os.scandir(res_dir):
        if not dir_file.is_dir():
            continue

        if dir_file.name.startswith(('values-en-rXA', 'values-ar-rXB')):
            continue

        is_default_values = dir_file.name == 'values'
        if parse_all_values:
            is_values = dir_file.name.startswith('values')
        else:
            is_values = is_default_values

        for resource_file in os.scandir(dir_file.path):
            if not resource_file.is_file():
                continue

            if resource_file.name.startswith('public-'):
                continue

            if resource_file.name == 'symbols.xml':
                continue

            # Some apps don't place their res directory directly under
            # the package directory
            # Only keep the resource directory name
            resources_dir_name = path.basename(res_dir)
            file_path = path.relpath(resource_file.path, res_dir)
            rel_path = path.join(resources_dir_name, file_path)

            if is_values:
                parse_xml_resource(
                    rel_path,
                    resource_file.path,
                    resources,
                    is_default_values,
                )
                continue

            # Inherited resources can be overwritten, do not assert
            # assert resource_file.name not in raw_resources, rel_path
            raw_resources[resource_file.name] = rel_path
            continue


def parse_overlay_resources(
    overlay_dir: str, resources_dir: str = RESOURCES_DIR
):
    resources: resources_dict = {}
    raw_resources: Dict[str, str] = {}

    res_dir = path.join(overlay_dir, resources_dir)
    if not path.exists(res_dir):
        return resources, raw_resources

    parse_package_resources_dir(
        res_dir,
        resources,
        raw_resources,
        parse_all_values=True,
    )

    return resources, raw_resources


def remove_overlay_resources(overlay_dir: str):
    res_dir = path.join(overlay_dir, RESOURCES_DIR)
    shutil.rmtree(res_dir, ignore_errors=True)


@functools.cache
def get_target_package_resources(res_dirs: Tuple[str]):
    resources: resources_dict = {}
    raw_resources: Dict[str, str] = {}

    for res_dir in res_dirs:
        parse_package_resources_dir(
            res_dir,
            resources,
            raw_resources,
        )

    return resources, raw_resources


def find_target_package_resources(
    target_packages: List[Tuple[str, Tuple[str]]],
    overlay_resources: resources_dict,
    overlay_xmls: Dict[str, str],
):
    max_matching_resources = 0
    best_resources = None

    for _, resource_dirs in target_packages:
        resources = get_target_package_resources(resource_dirs)
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
            max_matching_resources = matching_resources
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

    for attrib in element.attrib.values():
        if attrib == reference_name:
            return True

    for child_element in element:
        if is_referenced_resource_element(reference_name, child_element):
            return True

    return False


def get_reference_name(resource: Resource):
    return f'@{resource.tag}/{resource.name}'


def get_referencing_resource(
    resource: Resource,
    overlay_resources: resources_dict,
):
    reference_name = get_reference_name(resource)
    for overlay_resource in overlay_resources.values():
        if is_referenced_resource_element(
            reference_name,
            overlay_resource.element,
        ):
            return overlay_resource

    return None


def is_manifest_referencing_resource(
    resource: Resource,
    manifest_path: str,
):
    tree = etree.parse(manifest_path)
    root = tree.getroot()

    reference_name = get_reference_name(resource)

    return is_referenced_resource_element(reference_name, root)


def get_package_resource(
    package_resources: resources_dict,
    keys: Tuple[str, ...],
):
    package_resource = package_resources.get(keys)

    # Look for resources in the original package in the default values
    # directory if the specific values directory did not find it
    if package_resource is None:
        default_location_keys = ('', *keys[1:])
        package_resource = package_resources.get(default_location_keys)

    return package_resource


def fixup_incorrect_resources_type(
    overlay_resources: resources_dict,
    package_resources: resources_dict,
):
    removed_keys: Set[Tuple[str, ...]] = set()
    fixed_overlay_resources: resources_dict = {}
    wrong_type_resources: Set[Tuple[str, str, str]] = set()

    for keys, resource in overlay_resources.items():
        package_resource = get_package_resource(package_resources, keys)
        if package_resource is not None:
            continue

        correct_resource_type = get_correct_resource_type(
            resource,
            package_resources,
        )

        if correct_resource_type is None:
            continue

        wrong_type_resources.add(
            (resource.name, resource.tag, correct_resource_type)
        )

        new_keys = (keys[0], correct_resource_type, *keys[2:])
        resource.keys = new_keys
        resource.tag = correct_resource_type
        resource.element.tag = correct_resource_type

        removed_keys.add(keys)
        fixed_overlay_resources[new_keys] = resource

    for keys in removed_keys:
        del overlay_resources[keys]

    overlay_resources.update(fixed_overlay_resources)

    return wrong_type_resources


def group_overlay_resources_rel_path(
    overlay_resources: resources_dict,
    package_resources: resources_dict,
    manifest_path: str,
):
    grouped_resources: resources_grouped_dict = {}
    missing_resources: Set[str] = set()
    identical_resources: Set[str] = set()

    for keys, resource in overlay_resources.items():
        package_resource = get_package_resource(package_resources, keys)
        if package_resource is None:
            referencing_resource = get_referencing_resource(
                resource,
                overlay_resources,
            )
            if referencing_resource is not None:
                referencing_resource.references.append(resource)
                continue

            if not is_manifest_referencing_resource(resource, manifest_path):
                missing_resources.add(resource.name)
                continue

        if package_resource is not None:
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
            rel_path = path.join(
                resource.rel_dir_path, package_resource.xml_name
            )
        else:
            # Let the logic below place it at the end
            resource.index = -1

            # Keep the XML of the original resource as we couldn't find a
            # package resource for it
            rel_path = path.join(resource.rel_dir_path, resource.xml_name)

        grouped_resources.setdefault(rel_path, []).append(resource)

    for _, resources in grouped_resources.items():
        max_resources = len(resources)

        def resources_sort_key(r: Resource):
            if r.index == -1:
                return (r.name, max_resources)
            else:
                return (r.name, r.index)

        resources.sort(key=resources_sort_key)

    return (
        grouped_resources,
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


def read_raw_resources(
    overlay_path: str,
    overlay_raw_resources: Dict[str, str],
    package_raw_resources: Dict[str, str],
):
    # TODO: handle identical resources

    missing_raw_resources: List[str] = []
    raw_resources: Dict[str, str] = {}

    for raw_name, overlay_raw_rel_path in overlay_raw_resources.items():
        if raw_name not in package_raw_resources:
            missing_raw_resources.append(raw_name)
            continue

        package_raw_rel_path = package_raw_resources[raw_name]
        raw_path = path.join(overlay_path, overlay_raw_rel_path)
        with open(raw_path, 'rb') as raw:
            raw_resources[package_raw_rel_path] = raw.read()

    return raw_resources, missing_raw_resources


def write_overlay_raw_resources(
    raw_resources: Dict[str, str],
    output_path: str,
):
    for raw_rel_path, raw_data in raw_resources.items():
        raw_path = path.join(output_path, raw_rel_path)
        raw_dir_path = path.dirname(raw_path)
        os.makedirs(raw_dir_path, exist_ok=True)
        with open(raw_path, 'wb') as raw:
            raw.write(raw_data)

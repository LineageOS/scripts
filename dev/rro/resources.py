# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import functools
import os
import shutil
from os import path
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from lxml import etree

from rro.manifest import NAMESPACE
from utils.utils import (
    Color,
    color_print,
)
from utils.xml_utils import XML_COMMENT_TEXT, xml_element_canonical_str

Element = etree._Element  # type: ignore
Comment = etree._Comment  # type: ignore

TRANSLATABLE_KEY = 'translatable'
FEATURE_FLAG_KEY = 'featureFlag'
MSGID_KEY = 'msgid'
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
        element: Element,
        comments: List[Comment],
    ):
        self.index = index
        self.xml_name = xml_name
        self.rel_dir_path = rel_dir_path
        self.keys = keys
        self.tag = tag
        self.name = name
        self.element = element
        self.comments = comments

    def __repr__(self):
        s = '\n'
        s += f'{self.rel_dir_path}/{self.xml_name}:\n'
        s += f'{self.keys}\n'
        s += f'{xml_element_canonical_str(self.element)}\n'
        return s

    def __eq__(self, other: object):
        if not isinstance(other, Resource):
            return NotImplemented

        return (
            self.rel_dir_path == other.rel_dir_path
            and self.keys == other.keys
            and self.tag == other.tag
            and self.name == other.name
            and xml_element_canonical_str(self.element)
            == xml_element_canonical_str(other.element)
        )

    def __hash__(self) -> int:
        return hash(
            (
                self.rel_dir_path,
                self.keys,
                self.tag,
                self.name,
                xml_element_canonical_str(self.element),
            )
        )


resources_dict = Dict[Tuple[str, ...], Resource]
resources_grouped_dict = Dict[str, List[Resource]]


def resource_needs_quotes(s: str) -> bool:
    if not s:
        return False

    if s != s.strip():
        return True

    if any(c in s for c in '\n\t'):
        return True

    if ' '.join(s.split()) != s:
        return True

    return False


def node_has_space_after(node: Element):
    return node.tail is not None and node.tail.count('\n') > 1


UNITS = (
    'dip',
    'dp',
    'sp',
    'px',
    'pt',
    'in',
    'mm',
)


def normalize_node_text_dimens_units(text: str):
    left = text[: len(text) - len(text.lstrip())]
    right = text[len(text.rstrip()) :]
    core = text[len(left) : len(text) - len(right)]

    for u in UNITS:
        if not core.endswith(u):
            continue

        num = core[: -len(u)]

        if u == 'dip':
            u = 'dp'

        if num.endswith('.0'):
            num = num[:-2]

        core = num + u
        break

    return left + core + right


def normalize_node_text_string(text: str):
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        # Repalce non-breaking spaces with normal spaces
        text = text.replace('\u00a0', ' ')

        # Replace \' with '
        text = text.replace("\\'", "'")

        if resource_needs_quotes(text):
            return text

        return text[1:-1]

    return ' '.join(text.split())


def is_resource_removed(
    remove_resources: Set[Tuple[str | None, str]],
    resource: Resource,
    target_package: str,
):
    possible_entries: List[Tuple[str | None, str]] = [
        (None, resource.name),
        (target_package, resource.name),
    ]

    for entry in possible_entries:
        if entry in remove_resources:
            return True

    return False


def is_raw_resource_removed(
    remove_resources: Set[Tuple[str | None, str]],
    raw_rel_path: str,
    target_package: str,
):
    raw_name = path.basename(raw_rel_path)

    possible_entries: List[Tuple[str | None, str]] = [
        (None, raw_name),
        (None, raw_rel_path),
        (target_package, raw_name),
        (target_package, raw_rel_path),
    ]

    for entry in possible_entries:
        if entry in remove_resources:
            return True

    return False


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

    comments: List[Comment] = []
    index = 0
    for node in root:
        if isinstance(node, Comment):
            # Last element was not a comment, don't stack them
            # Or it was a comment, but they were not stacked
            last_node = node.getprevious()
            if not isinstance(last_node, Comment) or node_has_space_after(
                last_node
            ):
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

        if node.text is not None:
            # TODO: this is just a hack for wrong @*
            node.text = node.text.replace('@*', '@')

            if tag == 'dimen':
                node.text = normalize_node_text_dimens_units(node.text)

            if tag == 'string':
                node.text = normalize_node_text_string(node.text)

        # Overlays don't have translatable=false, remove it to fix
        # equality check
        if TRANSLATABLE_KEY in node.attrib:
            del node.attrib[TRANSLATABLE_KEY]

        if MSGID_KEY in node.attrib:
            del node.attrib[MSGID_KEY]

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
    raw_resources: Dict[str, bytes],
    parse_all_values: bool = False,
    keep_raw_resources_by_filename: bool = False,
):
    for dir_file in os.scandir(res_dir):
        if not dir_file.is_dir():
            continue

        pseudolocales = ('en-rXA', 'ar-rXB', 'en-rXC')
        if dir_file.name.startswith('values-') and any(
            locale in dir_file.name for locale in pseudolocales
        ):
            continue

        is_default_values = dir_file.name == 'values'
        is_any_values = dir_file.name.startswith('values')
        if parse_all_values:
            is_values = is_any_values
        else:
            is_values = is_default_values

        for resource_file in os.scandir(dir_file.path):
            if not resource_file.is_file():
                continue

            if (
                resource_file.name.startswith('public-')
                or resource_file.name == 'public.xml'
            ):
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

            if not is_any_values:
                assert len(Path(rel_path).parts) == 3, rel_path

                raw_resource_data = Path(resource_file).read_bytes()
                raw_resources[rel_path] = raw_resource_data

                if keep_raw_resources_by_filename:
                    # If there's no dash in the name of the directory of the
                    # resource, assume these are the base resources
                    # Implementing whole resource overlaying logic would be too
                    # complicated
                    # Keep track of them so overlays can check against them
                    rel_path_name = path.basename(rel_path)
                    rel_path_dir = path.dirname(rel_path)
                    rel_path_dir_name = path.basename(rel_path_dir)
                    if '-' not in rel_path_dir_name:
                        raw_resources[rel_path_name] = raw_resource_data


def parse_overlay_resources(
    overlay_dir: str,
    resources_dir: str = RESOURCES_DIR,
    remove_resources: Optional[Set[str]] = None,
):
    resources: resources_dict = {}
    raw_resources: Dict[str, bytes] = {}

    if remove_resources is None:
        remove_resources = set()

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
    raw_resources: Dict[str, bytes] = {}

    for res_dir in res_dirs:
        parse_package_resources_dir(
            res_dir,
            resources,
            raw_resources,
            keep_raw_resources_by_filename=True,
        )

    return resources, raw_resources


def find_target_package_resources(
    target_packages: List[Tuple[str, Tuple[str, ...]]],
    overlay_resources: resources_dict,
    overlay_raw_resources: Dict[str, bytes],
):
    best_matching_resources = 0
    best_resources = None
    best_raw_resources = None

    for _, resource_dirs in target_packages:
        package_resources, package_raw_resources = get_target_package_resources(
            resource_dirs,
        )

        matching_resources = 0
        if len(target_packages) != 1:
            for keys in overlay_resources.keys():
                if keys in package_resources:
                    matching_resources += 1
            for raw_resource_name in overlay_raw_resources:
                if raw_resource_name in package_raw_resources:
                    matching_resources += 1

        if matching_resources >= best_matching_resources:
            best_matching_resources = matching_resources
            best_resources = package_resources
            best_raw_resources = package_raw_resources

    assert best_resources is not None
    assert best_raw_resources is not None

    return best_resources, best_raw_resources


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
    element: Element,
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


def get_raw_resource_reference_name(rel_path: str):
    rel_path_name = path.basename(rel_path)
    rel_path_dir = path.dirname(rel_path)
    rel_path_dir_name = path.basename(rel_path_dir)
    rel_path_dir_name_parts = rel_path_dir_name.split('-')

    resource_name = path.splitext(rel_path_name)[0]
    resource_type_name = rel_path_dir_name_parts[0]

    return f'@{resource_type_name}/{resource_name}'


def get_referencing_resource(
    reference_name: str,
    overlay_resources: resources_dict,
):
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
        if 'type' in resource.element.attrib:
            correct_resource_type = resource.element.attrib['type']
            assert isinstance(correct_resource_type, str)
            del resource.element.attrib['type']
        else:
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
    package_resources_map: resources_dict,
    track_shadowed_resources: bool,
    is_kept_target_package: bool,
    remove_resources: Set[Tuple[str | None, str]],
    target_package: str,
):
    grouped_resources: resources_grouped_dict = {}
    missing_resources: Set[str] = set()
    identical_resources: Set[str] = set()
    shadowed_resources: Set[str] = set()
    removed_resources: Set[str] = set()

    def add_resource_to_package_resources_map(
        keys: Tuple[str, ...],
        rel_path: str,
        resource: Resource,
    ):
        updated_keys = (rel_path, *keys[1:])
        if updated_keys in package_resources_map:
            return False

        package_resources_map[updated_keys] = resource

        return True

    for keys, resource in overlay_resources.items():
        if is_resource_removed(remove_resources, resource, target_package):
            removed_resources.add(resource.name)
            continue

        # Let the logic below place it at the end if a package resource is not
        # found
        resource.index = -1

        # Keep the XML of the original resource as we couldn't find a
        # package resource for it
        rel_path = path.join(resource.rel_dir_path, resource.xml_name)

        package_resource = get_package_resource(package_resources, keys)
        if package_resource is None and not is_kept_target_package:
            reference_name = get_reference_name(resource)
            referencing_resource = get_referencing_resource(
                reference_name,
                overlay_resources,
            )
            is_manifest_referencing = is_manifest_referencing_resource(
                resource,
                manifest_path,
            )

            if referencing_resource is None and not is_manifest_referencing:
                # TODO: figure out if we should deal with shadowed resources
                # here
                missing_resources.add(resource.name)
                continue

        if package_resource is not None:
            # Keep the directory of the original resource, but place it in the
            # correct XML
            rel_path = path.join(
                resource.rel_dir_path, package_resource.xml_name
            )

            if track_shadowed_resources and xml_element_canonical_str(
                package_resource.element
            ) == xml_element_canonical_str(resource.element):
                # Even if a resource is identical to the AOSP value it should
                # overwrite following entries in other overlays
                if add_resource_to_package_resources_map(
                    keys,
                    rel_path,
                    resource,
                ):
                    identical_resources.add(resource.name)
                else:
                    shadowed_resources.add(resource.name)

                continue

            # TODO: find out if this is needed
            # resource.element.attrib[TRANSLATABLE_KEY] = 'false'
            resource.index = package_resource.index
            resource.comments = package_resource.comments

        if (
            not track_shadowed_resources
            or add_resource_to_package_resources_map(
                keys,
                rel_path,
                resource,
            )
        ):
            grouped_resources.setdefault(rel_path, []).append(resource)
        else:
            shadowed_resources.add(resource.name)

    for _, resources in grouped_resources.items():
        max_resources = len(resources)

        def resources_sort_key(r: Resource):
            if r.index == -1:
                return (max_resources, r.name)
            else:
                return (r.index, r.name)

        resources.sort(key=resources_sort_key)

    return (
        grouped_resources,
        missing_resources,
        identical_resources,
        shadowed_resources,
        removed_resources,
    )


def write_xml_resources(
    xml_path: str,
    resources: List[Resource],
    preserved_prefix: Optional[bytes] = None,
):
    xml_dir_path = path.dirname(xml_path)
    os.makedirs(xml_dir_path, exist_ok=True)

    root = etree.Element(RESOURCES_TAG)
    tree = etree.ElementTree(root)

    # Only add default header when we're NOT preserving an existing prefix
    if preserved_prefix is None:
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

            assert last_element is not None
            last_element.tail = next_line_spacing

        root.append(resource.element)
        last_element = resource.element

    if last_element is not None:
        last_element.tail = '\n'

    xml_body = etree.tostring(
        tree,
        pretty_print=True,
        encoding='utf-8',
    )

    with open(xml_path, 'wb') as o:
        if preserved_prefix is not None:
            o.write(preserved_prefix)
        else:
            o.write(b'<?xml version="1.0" encoding="utf-8"?>\n')
        o.write(xml_body)


def write_grouped_resources(
    grouped_resources: resources_grouped_dict,
    output_path: str,
    preserved_prefixes: Dict[str, bytes],
):
    for rel_path, resources in grouped_resources.items():
        xml_path = path.join(output_path, rel_path)
        preserved = preserved_prefixes.get(xml_path)

        write_xml_resources(
            xml_path,
            resources,
            preserved_prefix=preserved,
        )


def group_overlay_raw_resources(
    overlay_raw_resources: Dict[str, bytes],
    overlay_resources: resources_dict,
    package_raw_resources: Dict[str, bytes],
    remove_resources: Set[Tuple[str | None, str]],
    target_package: str,
):
    identical_raw_resources: List[str] = []
    missing_raw_resources: List[str] = []
    removed_raw_resources: List[str] = []
    raw_resources: Dict[str, bytes] = {}

    for raw_rel_path, raw_resource_data in overlay_raw_resources.items():
        if is_raw_resource_removed(
            remove_resources,
            raw_rel_path,
            target_package,
        ):
            removed_raw_resources.append(raw_rel_path)
            continue

        raw_name = path.basename(raw_rel_path)

        package_raw_name = raw_rel_path

        if package_raw_name not in package_raw_resources:
            package_raw_name = raw_name

        # If there's no raw resource with the same name in the package, try
        # finding if this raw resource is referenced by other non-raw resources
        # in the overlay
        referencing_resource = None
        if package_raw_name not in package_raw_resources:
            reference_name = get_raw_resource_reference_name(raw_rel_path)
            referencing_resource = get_referencing_resource(
                reference_name, overlay_resources
            )

        package_raw_resource_data = package_raw_resources.get(package_raw_name)
        if package_raw_resource_data is None and referencing_resource is None:
            missing_raw_resources.append(raw_rel_path)
            continue

        if raw_resource_data == package_raw_resource_data:
            identical_raw_resources.append(raw_rel_path)
            continue

        raw_resources[raw_rel_path] = raw_resource_data

    return (
        raw_resources,
        missing_raw_resources,
        identical_raw_resources,
        removed_raw_resources,
    )


def write_overlay_raw_resources(
    raw_resources: Dict[str, bytes],
    output_path: str,
):
    for raw_rel_path, raw_data in raw_resources.items():
        raw_path = path.join(output_path, raw_rel_path)
        raw_dir_path = path.dirname(raw_path)
        os.makedirs(raw_dir_path, exist_ok=True)
        with open(raw_path, 'wb') as raw:
            raw.write(raw_data)

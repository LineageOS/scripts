# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import functools
import os
from abc import ABC, abstractmethod
from fnmatch import fnmatch
from os import path
from pathlib import Path
from typing import (
    Callable,
    Dict,
    FrozenSet,
    List,
    Literal,
    Optional,
    Set,
    Tuple,
    Union,
)

from lxml import etree

from rro.manifest import NAMESPACE
from utils.utils import (
    Color,
    color_print,
)
from utils.xml_utils import (
    XML_COMMENT_TEXT,
    xml_attrib_matches,
    xml_element_canonical_str,
    xml_read_prefix_before_tag,
)

Element = etree._Element  # type: ignore
Comment = etree._Comment  # type: ignore

TRANSLATABLE_KEY = 'translatable'
FEATURE_FLAG_KEY = 'featureFlag'
MSGID_KEY = 'msgid'
RESOURCES_TAG = 'resources'
RESOURCES_DIR = 'res'


@functools.cache
def strip_rel_dir_qualifiers(rel_dir_path: str):
    parts = Path(rel_dir_path).parts

    if '-' not in parts[-1]:
        return rel_dir_path

    resource_type = parts[-1]
    stripped_resource_type = resource_type.split('-')[0]
    stripped_rel_dir_path = Path(*parts[:-1], stripped_resource_type)

    return str(stripped_rel_dir_path)


class Resource(ABC):
    def __init__(
        self,
        rel_dir_path: str,
        file_name: str,
    ):
        self.rel_dir_path = rel_dir_path
        self.file_name = file_name

    @abstractmethod
    def copy(self, rel_dir_path: Optional[str] = None) -> Resource: ...

    @property
    @abstractmethod
    def rel_path(self) -> str: ...

    @property
    @abstractmethod
    def keys(self) -> Tuple[str, ...]: ...

    @property
    @abstractmethod
    def reference_name(self) -> str: ...

    @abstractmethod
    def __eq__(self, other: object) -> bool: ...

    @abstractmethod
    def __hash__(self) -> int: ...

    def __lt__(self, other: object):
        if not isinstance(other, Resource):
            return NotImplemented

        return self.keys < other.keys


class RawResource(Resource):
    def __init__(
        self,
        rel_dir_path: str,
        file_name: str,
        data: bytes,
    ):
        super().__init__(rel_dir_path, file_name)

        self.data = data

    def copy(
        self,
        rel_dir_path: Optional[str] = None,
    ):
        return RawResource(
            rel_dir_path if rel_dir_path is not None else self.rel_dir_path,
            self.file_name,
            self.data,
        )

    @property
    def reference_name(self):
        resource_type = strip_rel_dir_qualifiers(self.rel_dir_path)
        resource_name = path.splitext(self.file_name)[0]

        return f'@{resource_type}/{resource_name}'

    @property
    def rel_path(self):
        return path.join(self.rel_dir_path, self.file_name)

    @property
    def keys(self):
        return (
            self.rel_dir_path,
            self.file_name,
        )

    def __eq__(self, other: object):
        if not isinstance(other, RawResource):
            return False

        return (
            self.rel_dir_path == other.rel_dir_path
            and self.file_name == other.file_name
            and self.data == other.data
        )

    def __hash__(self) -> int:
        return hash(
            (
                self.rel_dir_path,
                self.file_name,
                self.data,
            )
        )

    def __repr__(self):
        return f'{self.rel_dir_path}/{self.file_name}'


class XMLResource(Resource):
    def __init__(
        self,
        index: int,
        file_name: str,
        rel_dir_path: str,
        tag: str,
        name: str,
        element: Element,
        comments: List[Comment],
        product: str,
        feature_flag: str,
    ):
        super().__init__(rel_dir_path, file_name)

        self.index = index
        self.tag = tag
        self.name = name
        self.element = element
        self.comments = comments
        self.product = product
        self.feature_flag = feature_flag

    def copy(
        self,
        rel_dir_path: Optional[str] = None,
        index: Optional[int] = None,
        file_name: Optional[str] = None,
        tag: Optional[str] = None,
        attrib: Optional[Dict[str | bytes, str | bytes]] = None,
        comments: Optional[List[Comment]] = None,
    ):
        element = None
        if tag is not None or attrib is not None:
            element = etree.fromstring(etree.tostring(self.element))

        if tag is not None:
            assert element is not None
            element.tag = tag

        if attrib is not None:
            assert element is not None
            element.attrib.clear()

            for k, v in attrib.items():
                element.attrib[k] = v

        return XMLResource(
            index if index is not None else self.index,
            file_name if file_name is not None else self.file_name,
            rel_dir_path if rel_dir_path is not None else self.rel_dir_path,
            tag if tag is not None else self.tag,
            self.name,
            element if element is not None else self.element,
            comments if comments is not None else self.comments,
            self.product,
            self.feature_flag,
        )

    @property
    def reference_name(self):
        return f'@{self.tag}/{self.name}'

    @property
    def rel_path(self):
        return path.join(self.rel_dir_path, self.file_name)

    @property
    def keys(self):
        return (
            self.rel_dir_path,
            self.name,
            self.product,
            self.feature_flag,
        )

    def __repr__(self):
        s = f'{self.rel_dir_path}/{self.file_name}:\n'
        s += etree.tostring(self.element, encoding='unicode')
        s += '\n'
        return s

    def __eq__(self, other: object):
        if not isinstance(other, XMLResource):
            return False

        return (
            self.rel_dir_path == other.rel_dir_path
            and self.tag == other.tag
            and self.name == other.name
            and self.product == other.product
            and self.feature_flag == other.feature_flag
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
resources_grouped_dict = Dict[str, List[XMLResource]]


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


def parse_xml_resources(
    rel_dir_path: str,
    file_name: str,
    data: bytes,
    resources: Dict[Tuple[str, ...], Resource],
):
    root = etree.fromstring(data)

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

        resource = XMLResource(
            index,
            file_name,
            rel_dir_path,
            tag,
            name,
            node,
            comments,
            product,
            feature_flag,
        )
        index += 1

        # Assign the same comment to entries following each other without a
        # newline
        if node_has_space_after(node):
            comments = []

        if resource.keys in resources:
            # color_print(
            #     f'{resource.rel_path}: {resource.reference_name} already found',
            #     color=Color.YELLOW,
            # )
            continue

        resources[resource.keys] = resource


def resources_reference_name_sorted(resources: Set[Resource]):
    return sorted(set(r.reference_name for r in resources))


def sorted_scandir(dir_path: str):
    return sorted(os.scandir(dir_path), key=lambda e: e.path)


def parse_package_resources_dir(
    res_dir: str,
    resources: Dict[Tuple[str, ...], Resource],
    parse_all_values: bool = False,
):
    for dir_file in sorted_scandir(res_dir):
        if not dir_file.is_dir():
            continue

        pseudolocales = ('en-rXA', 'ar-rXB', 'en-rXC')
        if dir_file.name.startswith('values-') and any(
            locale in dir_file.name for locale in pseudolocales
        ):
            continue

        is_values = dir_file.name.startswith('values')
        if is_values and not parse_all_values and dir_file.name != 'values':
            continue

        for resource_file in sorted_scandir(dir_file.path):
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
            rel_path = path.relpath(resource_file.path, res_dir)
            rel_dir_path = path.dirname(rel_path)
            file_name = path.basename(rel_path)
            data = Path(resource_file.path).read_bytes()

            if is_values:
                parse_xml_resources(
                    rel_dir_path,
                    file_name,
                    data,
                    resources,
                )
            else:
                resource = RawResource(
                    rel_dir_path,
                    file_name,
                    data,
                )
                resources[resource.keys] = resource


def parse_overlay_resources(
    resources_path: str,
    remove_resources: Optional[Set[str]] = None,
) -> Set[Resource]:
    resources: Dict[Tuple[str, ...], Resource] = {}

    if remove_resources is None:
        remove_resources = set()

    if not path.exists(resources_path):
        return set()

    parse_package_resources_dir(
        resources_path,
        resources,
        parse_all_values=True,
    )

    return set(resources.values())


@functools.cache
def get_target_package_resources(res_dirs: Tuple[str]):
    resources: Dict[Tuple[str, ...], Resource] = {}

    for res_dir in res_dirs:
        parse_package_resources_dir(
            res_dir,
            resources,
        )

    return resources


def find_target_package_resources(
    target_packages: List[Tuple[str, str, Tuple[str, ...]]],
    overlay_resources: Set[Resource],
):
    if len(target_packages) == 1:
        _, module_name, resource_dirs = target_packages[0]
        package_resources = get_target_package_resources(
            resource_dirs,
        )
        return package_resources, module_name

    best_matching_resources = 0
    best_module_name = None
    best_resources = None

    for _, module_name, resource_dirs in target_packages:
        package_resources = get_target_package_resources(
            resource_dirs,
        )

        matching_resources = 0
        for resource in overlay_resources:
            package_resource = get_package_resource(
                package_resources,
                resource,
            )
            if package_resource is not None:
                matching_resources += 1
                continue

            unqualified_resource = get_unqualified_package_resource(
                package_resources,
                resource,
            )
            if unqualified_resource is not None:
                matching_resources += 1
                continue

        if matching_resources > best_matching_resources:
            best_matching_resources = matching_resources
            best_module_name = module_name
            best_resources = package_resources

    return best_resources, best_module_name


def is_referenced_resource_element(
    reference_name: str,
    element: Element,
):
    if element.text is not None and element.text.strip() == reference_name:
        return True

    if element.tail is not None and element.tail.strip() == reference_name:
        return True

    for attrib in element.attrib.values():
        if attrib == reference_name:
            return True

    for child_element in element:
        if is_referenced_resource_element(reference_name, child_element):
            return True

    return False


def get_referencing_resource(
    overlay_resources: Set[Resource],
    reference_name: str,
):
    for resource in overlay_resources:
        if not isinstance(resource, XMLResource):
            continue

        if is_referenced_resource_element(
            reference_name,
            resource.element,
        ):
            return resource

    return None


def get_resource_element_references(
    element: Element,
    referenced_resources: Optional[Set[str]] = None,
):
    if referenced_resources is None:
        referenced_resources = set()

    if element.text is not None:
        element_text = element.text.strip()
        if element_text.startswith('@'):
            referenced_resources.add(element_text)

    if element.tail is not None:
        element_tail = element.tail.strip()
        if element_tail.startswith('@'):
            referenced_resources.add(element_tail)

    for attrib in element.attrib.values():
        assert isinstance(attrib, str)
        if attrib.startswith('@'):
            referenced_resources.add(attrib)

    for child_element in element:
        get_resource_element_references(child_element, referenced_resources)

    return referenced_resources


def remove_resources_referenced(
    resources: Set[Resource],
    removed_resources: Set[Resource],
):
    graph: Dict[str, Set[str]] = {}
    for r in resources | removed_resources:
        name = r.reference_name

        refs: Set[str] = set()
        if isinstance(r, XMLResource):
            refs = get_resource_element_references(r.element)

        graph.setdefault(name, set()).update(refs)

        for ref in refs:
            graph.setdefault(ref, set()).add(name)

    removed_names = {r.reference_name for r in removed_resources}

    return {
        r
        for r in resources
        if not (graph.get(r.reference_name, set()) & removed_names)
    }


def get_unqualified_package_resource(
    package_resources: resources_dict,
    resource: Resource,
):
    rel_dir_path = resource.rel_dir_path
    stripped_rel_dir_path = strip_rel_dir_qualifiers(rel_dir_path)
    unqualified_resource = resource.copy(rel_dir_path=stripped_rel_dir_path)
    return package_resources.get(unqualified_resource.keys)


def get_package_resource(
    package_resources: resources_dict,
    resource: Resource,
):
    return package_resources.get(resource.keys)


def overlay_resources_remove_add(
    overlay_resources: Set[Resource],
    removed_resources: Set[Resource],
    added_resources: Set[Resource],
):
    for resource in removed_resources:
        overlay_resources.remove(resource)

    for resource in added_resources:
        overlay_resources.add(resource)


def overlay_resources_process(
    overlay_resources: Set[Resource],
    fn: Callable[
        [Resource],
        Union[
            # Replace
            Tuple[
                Resource,
                Resource,
            ],
            # Remove
            Literal[True],
            # Skip
            None,
        ],
    ],
):
    removed_resources: Set[Resource] = set()
    added_resources: Set[Resource] = set()

    for resource in overlay_resources:
        result = fn(resource)
        if result is None:
            continue

        if result is True:
            removed_resources.add(resource)
            continue

        remove_resource, add_resource = result
        removed_resources.add(remove_resource)
        added_resources.add(add_resource)

    for resource in removed_resources:
        overlay_resources.remove(resource)

    for resource in added_resources:
        overlay_resources.add(resource)

    return removed_resources, added_resources


def is_resource_entry_wildcard(resource_entry: str):
    return any(c in resource_entry for c in '*?[')


@functools.cache
def resource_entries_wildcards(resource_entries: FrozenSet[str]):
    return frozenset(
        resource_entry
        for resource_entry in resource_entries
        if is_resource_entry_wildcard(resource_entry)
    )


def is_resource_in_entries(
    resource_entries: FrozenSet[str],
    resource: Resource,
):
    if not resource_entries:
        return False

    if isinstance(resource, RawResource):
        if resource.file_name in resource_entries:
            return True
        if resource.rel_path in resource_entries:
            return True

        for pattern in resource_entries_wildcards(resource_entries):
            if fnmatch(resource.file_name, pattern):
                return True
            if fnmatch(resource.rel_path, pattern):
                return True

    elif isinstance(resource, XMLResource):
        if resource.name in resource_entries:
            return True

        for pattern in resource_entries_wildcards(resource_entries):
            if fnmatch(resource.name, pattern):
                return True
    else:
        assert False

    return False


def overlay_resources_remove(
    overlay_resources: Set[Resource],
    remove_resources: FrozenSet[str],
):
    def remove_resource(resource: Resource):
        if is_resource_in_entries(remove_resources, resource):
            return True

    removed_resources, _ = overlay_resources_process(
        overlay_resources,
        remove_resource,
    )

    return removed_resources


def overlay_resources_fixup_tag(
    overlay_resources: Set[Resource],
    package_resources: resources_dict,
):
    wrong_tag_resources: Set[Tuple[str, str]] = set()

    def fixup_resource_tag(resource: Resource):
        if not isinstance(resource, XMLResource):
            return

        package_resource = get_unqualified_package_resource(
            package_resources,
            resource,
        )
        if package_resource is None:
            return

        assert isinstance(package_resource, XMLResource)

        attrib = dict(resource.element.attrib)

        def assign_attrib(name: str):
            package_attrib = package_resource.element.attrib.get(name)
            if resource.element.attrib.get(name) == package_attrib:
                return False

            if package_attrib is None:
                attrib.pop(name)
            else:
                attrib[name] = package_attrib

            return True

        tag = None
        if resource.tag != package_resource.tag:
            tag = package_resource.tag

        type_set = assign_attrib('type')
        format_set = assign_attrib('format')

        if tag is None and not type_set and not format_set:
            return

        new_resource = resource.copy(
            tag=tag,
            attrib=attrib,
        )

        wrong_tag_resources.add(
            (
                resource.reference_name,
                new_resource.reference_name,
            )
        )

        return resource, new_resource

    overlay_resources_process(overlay_resources, fixup_resource_tag)

    return wrong_tag_resources


def overlay_resources_remove_missing(
    overlay_resources: Set[Resource],
    package_resources: resources_dict,
    manifest_path: str,
    keep_resources: FrozenSet[str],
):
    manifest_tree = etree.parse(manifest_path)
    manifest_root = manifest_tree.getroot()

    kept_resources: Set[Resource] = set()

    def remove_missing_resource(resource: Resource):
        if is_resource_in_entries(keep_resources, resource):
            kept_resources.add(resource)
            return

        package_resource = get_package_resource(
            package_resources,
            resource,
        )
        if package_resource is not None:
            return

        package_resource = get_unqualified_package_resource(
            package_resources,
            resource,
        )
        if package_resource is not None:
            return

        referencing_resource = get_referencing_resource(
            overlay_resources,
            resource.reference_name,
        )
        if referencing_resource is not None:
            return

        is_manifest_referencing = is_referenced_resource_element(
            resource.reference_name,
            manifest_root,
        )
        if is_manifest_referencing:
            return

        return True

    removed_resources, _ = overlay_resources_process(
        overlay_resources,
        remove_missing_resource,
    )

    return removed_resources, kept_resources


def overlay_resource_fixup_from_package(
    overlay_resources: Set[Resource],
    package_resources: resources_dict,
):
    def fixup_resource_from_package(resource: Resource):
        if not isinstance(resource, XMLResource):
            return

        # Let the logic below place it at the end if a package resource is not
        # found
        index = -1
        comments = None
        file_name = resource.file_name

        # Preffer the unqualified resource since it it most likely to
        # have comments
        package_resource = get_unqualified_package_resource(
            package_resources,
            resource,
        )
        if package_resource is None:
            package_resource = get_package_resource(
                package_resources,
                resource,
            )

        if package_resource is not None:
            assert isinstance(package_resource, XMLResource)
            index = package_resource.index
            comments = package_resource.comments
            file_name = package_resource.file_name

        return resource, resource.copy(
            index=index,
            comments=comments,
            file_name=file_name,
        )

    overlay_resources_process(
        overlay_resources,
        fixup_resource_from_package,
    )


def overlay_resource_remove_shadowed(
    overlay_resources: Set[Resource],
    package_resources_map: Dict[Tuple[str, ...], str],
    package: str,
):
    shadowed_resources: Set[Tuple[str, str]] = set()

    def remove_shadowed_resource(resource: Resource):
        if resource.keys not in package_resources_map:
            package_resources_map[resource.keys] = package
            return

        shadowed_resources.add(
            (
                resource.reference_name,
                package_resources_map[resource.keys],
            )
        )
        return True

    overlay_resources_process(
        overlay_resources,
        remove_shadowed_resource,
    )

    return shadowed_resources


def overlay_resource_remove_identical(
    overlay_resources: Set[Resource],
    package_resources: resources_dict,
):
    def remove_identical_resource(resource: Resource):
        package_resource = get_package_resource(
            package_resources,
            resource,
        )
        if package_resource is None:
            package_resource = get_unqualified_package_resource(
                package_resources,
                resource,
            )

        if package_resource is None:
            return

        if resource != package_resource:
            return

        return True

    removed_resources, _ = overlay_resources_process(
        overlay_resources,
        remove_identical_resource,
    )

    return removed_resources


def overlay_resource_split_by_type(
    overlay_resources: Set[Resource],
):
    resources: Set[XMLResource] = set()
    raw_resources: Set[RawResource] = set()

    for resource in overlay_resources:
        if isinstance(resource, RawResource):
            raw_resources.add(resource)
        elif isinstance(resource, XMLResource):
            resources.add(resource)
        else:
            assert False

    return resources, raw_resources


def overlay_resources_group_by_rel_path(
    overlay_resources: Set[XMLResource],
):
    grouped_resources: resources_grouped_dict = {}

    for resource in overlay_resources:
        grouped_resources.setdefault(resource.rel_path, []).append(resource)

    for _, resources in grouped_resources.items():
        resources.sort(key=lambda r: (r.index == -1, r.index, r.name))

    return grouped_resources


def attrib_needs_aapt_raw(
    _attrib_key: str | bytes,
    attrib_value: str | bytes,
):
    if not len(attrib_value) > 1:
        return False

    if isinstance(attrib_value, bytes):
        return attrib_value.startswith(b'0')
    elif isinstance(attrib_value, str):
        return attrib_value.startswith('0')
    else:
        assert False


def raw_resources_need_aapt_raw(raw_resources: Set[RawResource]):
    for raw_resource in raw_resources:
        if not raw_resource.file_name.endswith('.xml'):
            continue

        try:
            if xml_attrib_matches(raw_resource.data, attrib_needs_aapt_raw):
                return raw_resource
        except etree.XMLSyntaxError:
            pass

    return None


def write_xml_resources(
    xml_path: str,
    resources: List[XMLResource],
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
    resources_dir: str,
    preserved_prefixes: Optional[Dict[str, bytes]],
):
    if preserved_prefixes is None:
        preserved_prefixes = {}

    for rel_path, resources in grouped_resources.items():
        xml_path = path.join(output_path, resources_dir, rel_path)
        preserved = preserved_prefixes.get(xml_path)

        write_xml_resources(
            xml_path,
            resources,
            preserved_prefix=preserved,
        )


def write_overlay_raw_resources(
    raw_resources: Set[RawResource],
    output_path: str,
    resources_dir: str,
):
    for raw_resource in raw_resources:
        raw_path = path.join(output_path, resources_dir, raw_resource.rel_path)
        raw_dir_path = path.dirname(raw_path)
        os.makedirs(raw_dir_path, exist_ok=True)
        with open(raw_path, 'wb') as raw:
            raw.write(raw_resource.data)


def read_xml_resources_prefix(
    overlay_resources: Set[Resource],
    output_path: str,
    extra_paths: List[str],
):
    rel_xml_paths: Set[str] = set()

    for resource in overlay_resources:
        if not isinstance(resource, XMLResource):
            continue

        rel_xml_paths.add(resource.rel_path)

    rel_xml_paths.update(extra_paths)

    preserved_prefixes: Dict[str, bytes] = {}
    for rel_xml_path in rel_xml_paths:
        if rel_xml_path in preserved_prefixes:
            continue

        existing_xml_path = path.join(output_path, rel_xml_path)

        preserved = xml_read_prefix_before_tag(existing_xml_path, 'resources')
        if not preserved:
            continue

        preserved_prefixes[existing_xml_path] = preserved

    return preserved_prefixes

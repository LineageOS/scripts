# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import functools
import os
import re
from abc import ABC, abstractmethod
from collections import defaultdict
from enum import Enum, auto
from fnmatch import fnmatch
from os import path
from typing import (
    Callable,
    Dict,
    FrozenSet,
    Iterable,
    List,
    Literal,
    Optional,
    Set,
    Tuple,
    TypeGuard,
    Union,
)

from lxml import etree

from apk.arsc_decode_string import ASCII_WHITESPACE, str_needs_whitespace_quotes
from rro.manifest import NAMESPACE
from utils.xml_utils import (
    XML_COMMENT_TEXT,
    xml_attrib_matches,
    xml_element_canonical_str,
    xml_read_prefix_before_tag,
)

Element = etree._Element  # type: ignore
Comment = etree._Comment  # type: ignore

TRANSLATABLE_KEY = 'translatable'
FEATURE_FLAG_KEY = f'{{{NAMESPACE}}}featureFlag'
MSGID_KEY = 'msgid'
RESOURCES_TAG = 'resources'
RESOURCES_DIR = 'res'
NAME_KEY = 'name'
PRODUCT_KEY = 'product'
DEFAULT_PRODUCT = 'default'
DIMEN_TAG = 'dimen'
STRING_TAG = 'string'


class ResourceType(Enum):
    XML = auto()
    RAW = auto()


class Resource(ABC):
    rel_path: str
    reference_name: str

    def __init__(
        self,
        rel_dir_path: str,
        name: str,
        resource_type: ResourceType,
    ):
        self.rel_dir_path = rel_dir_path
        self.is_default = '-' not in self.rel_dir_path
        self.name = name
        self.type = resource_type

    @property
    @abstractmethod
    def keys(self) -> Tuple[str, ...]: ...

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
        name: str,
        data: Optional[bytes],
    ):
        super().__init__(rel_dir_path, name, ResourceType.RAW)

        self.data = data
        self.__hash_keys = (
            self.rel_dir_path,
            self.name,
            0 if self.data is None else len(self.data),
        )
        self.__hash = hash(self.__hash_keys)
        self.rel_path = f'{self.rel_dir_path}/{self.name}'

        resource_type = rel_dir_path.split('-', maxsplit=1)[0]
        resource_name = path.splitext(self.name)[0]
        self.reference_name = f'@{resource_type}/{resource_name}'

    @property
    def keys(self):
        return (
            self.rel_dir_path,
            self.name,
        )

    def __eq__(self, other: object):
        if not isinstance(other, RawResource):
            return False

        if self.__hash_keys != other.__hash_keys:
            return False

        return self.data == other.data

    def __hash__(self) -> int:
        return self.__hash

    def __repr__(self):
        return f'{self.rel_dir_path}/{self.name}'


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
        super().__init__(rel_dir_path, name, ResourceType.XML)

        self.index = index
        self.tag = tag
        self.file_name = file_name
        self.element = element
        self.comments = comments
        self.product = product
        self.feature_flag = feature_flag
        self.reference_name = f'@{self.tag}/{self.name}'
        self.__element_str = xml_element_canonical_str(self.element)
        self.__hash_keys = (
            self.rel_dir_path,
            self.tag,
            self.name,
            self.product,
            self.feature_flag,
            self.__element_str,
        )
        self.__hash = hash(self.__hash_keys)
        self.rel_path = f'{self.rel_dir_path}/{self.file_name}'

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
    def keys(self):
        return (
            self.rel_dir_path,
            self.name,
            self.product,
            self.feature_flag,
        )

    def __repr__(self):
        s = f'{self.rel_dir_path}/{self.file_name}:\n'
        s += etree.tostring(self.element, encoding='unicode').strip()
        s += '\n'
        return s

    def __eq__(self, other: object):
        if not isinstance(other, XMLResource):
            return False

        return self.__hash_keys == other.__hash_keys

    def __hash__(self) -> int:
        return self.__hash


def is_xml_resource(r: Resource) -> TypeGuard[XMLResource]:
    return r.type is ResourceType.XML


def is_raw_resource(r: Resource) -> TypeGuard[RawResource]:
    return r.type is ResourceType.RAW


def is_by_rel_path_raw_resources(
    resources: Set[Resource],
) -> TypeGuard[Set[RawResource]]:
    if not len(resources):
        return True

    # Raw resources shouldn't be able to appear multiple times for the same
    # relative path, use that to optimize the check
    if len(resources) == 1 and is_raw_resource(next(iter(resources))):
        return True

    return False


def is_by_rel_path_xml_resources(
    resources: Set[Resource],
) -> TypeGuard[Set[XMLResource]]:
    if not len(resources):
        return True

    if not is_by_rel_path_raw_resources(resources):
        return True

    return False


resource_str_map = Dict[str, Set[Resource]]


class ResourceMap:
    def __init__(
        self,
        resources: Optional[Set[Resource]] = None,
        by_name: bool = False,
        by_reference_name: bool = False,
        by_rel_path: bool = False,
        by_references: bool = False,
    ):
        self.__all: Set[Resource] = set()

        self.__by_name: Optional[resource_str_map] = None
        if by_name:
            self.__by_name = defaultdict(set)

        self.__by_reference_name: Optional[resource_str_map] = None
        if by_reference_name:
            self.__by_reference_name = defaultdict(set)

        self.__by_rel_path: Optional[resource_str_map] = None
        if by_rel_path:
            self.__by_rel_path = defaultdict(set)

        self.__references_to_resource: Optional[Dict[str, Set[Resource]]] = None
        self.__resource_to_references: Optional[Dict[Resource, Set[str]]] = None
        if by_references:
            self.__references_to_resource = defaultdict(set)
            self.__resource_to_references = defaultdict(set)

        if resources:
            self.add_many(resources)

    def __eq__(self, other: object):
        if not isinstance(other, ResourceMap):
            return NotImplemented

        return self.__all == other.__all

    def __iter__(self):
        return iter(self.__all)

    def __len__(self):
        return len(self.__all)

    def __contains__(self, item: Resource):
        return item in self.__all

    def __init_by_name(self):
        if self.__by_name is not None:
            return self.__by_name

        self.__by_name = defaultdict(set)
        for resource in self.__all:
            self.__by_name[resource.name].add(resource)

        return self.__by_name

    def __init_by_reference_name(self):
        if self.__by_reference_name is not None:
            return self.__by_reference_name

        self.__by_reference_name = defaultdict(set)
        for resource in self.__all:
            self.__by_reference_name[resource.reference_name].add(resource)

        return self.__by_reference_name

    def __init_by_rel_path(self):
        if self.__by_rel_path is not None:
            return self.__by_rel_path

        self.__by_rel_path = defaultdict(set)
        for resource in self.__all:
            self.__by_rel_path[resource.rel_path].add(resource)

            if isinstance(resource, RawResource):
                # Enforce that the same raw resource does not appear multiple times
                # for the same path, as other logic depends on this
                assert len(self.__by_rel_path[resource.rel_path]) == 1, resource

        return self.__by_rel_path

    def __init_ref_map(self):
        if (
            self.__resource_to_references is not None
            and self.__references_to_resource is not None
        ):
            return

        self.__resource_to_references = defaultdict(set)
        self.__references_to_resource = defaultdict(set)
        for resource in self.__all:
            self.__add_resource_refs(resource)

    def __remove_resource_refs(self, resource: Resource):
        if (
            self.__resource_to_references is None
            or self.__references_to_resource is None
        ):
            return

        refs = self.__resource_to_references.pop(resource, None)
        if refs is None:
            return

        for ref in refs:
            s = self.__references_to_resource.get(ref)
            if not s:
                continue
            s.discard(resource)
            if not s:
                del self.__references_to_resource[ref]

    def __add_resource_refs(self, resource: Resource):
        if not is_xml_resource(resource):
            return

        refs = get_resource_element_references(resource.element)

        assert self.__resource_to_references is not None
        assert self.__references_to_resource is not None

        self.__resource_to_references[resource].update(refs)

        for ref in refs:
            self.__references_to_resource[ref].add(resource)

    def add(self, resource: Resource):
        self.__all.add(resource)
        if (
            self.__resource_to_references is not None
            and self.__references_to_resource is not None
        ):
            self.__add_resource_refs(resource)
        if self.__by_name is not None:
            self.__by_name[resource.name].add(resource)

        if self.__by_reference_name is not None:
            self.__by_reference_name[resource.reference_name].add(resource)

        if self.__by_rel_path is not None:
            self.__by_rel_path[resource.rel_path].add(resource)

            if isinstance(resource, RawResource):
                # Enforce that the same raw resource does not appear multiple times
                # for the same path, as other logic depends on this
                assert len(self.__by_rel_path[resource.rel_path]) == 1, resource

    def add_many(self, resources: Set[Resource]):
        self.__all.update(resources)

        do_refs = (
            self.__resource_to_references is not None
            and self.__references_to_resource is not None
        )
        by_name = self.__by_name
        by_ref = self.__by_reference_name
        by_path = self.__by_rel_path

        for resource in resources:
            if do_refs:
                self.__add_resource_refs(resource)

            if by_name is not None:
                by_name[resource.name].add(resource)

            if by_ref is not None:
                by_ref[resource.reference_name].add(resource)

            if by_path is not None:
                s = by_path[resource.rel_path]
                s.add(resource)
                if isinstance(resource, RawResource):
                    assert len(s) == 1, resource

    def __index_remove(
        self,
        index: Optional[resource_str_map],
        key: str,
        resource: Resource,
    ):
        if index is None:
            return

        s = index.get(key)
        if s is None:
            raise KeyError(key)

        s.remove(resource)

        if not s:
            del index[key]

    def remove(self, resource: Resource):
        self.__all.remove(resource)

        self.__remove_resource_refs(resource)

        self.__index_remove(
            self.__by_name,
            resource.name,
            resource,
        )
        self.__index_remove(
            self.__by_reference_name,
            resource.reference_name,
            resource,
        )
        self.__index_remove(
            self.__by_rel_path,
            resource.rel_path,
            resource,
        )

    def remove_many(self, resources: Iterable[Resource]):
        for r in resources:
            self.remove(r)

    def all(self) -> Set[Resource]:
        return self.__all

    def by_rel_path(self):
        return self.__init_by_rel_path().items()

    def by_name(self, name: str):
        return self.__init_by_name()[name]

    def by_reference_name(self, reference_name: str):
        return self.__init_by_reference_name()[reference_name]

    def one_by_name(self, name: str) -> Optional[Resource]:
        s = self.__init_by_name()[name]
        if not s:
            return None

        return next(iter(s))

    def __reference_names_to_resource(self, refs: Set[str]):
        resources: Set[Resource] = set()
        for ref in refs:
            resources.update(self.by_reference_name(ref))
        return resources

    def resources_referenced_by(self, resource: Resource):
        self.__init_ref_map()
        assert self.__resource_to_references is not None
        refs = self.__resource_to_references[resource]
        return self.__reference_names_to_resource(refs)

    def resources_referencing(self, resource: Resource):
        self.__init_ref_map()
        assert self.__references_to_resource is not None
        return self.__references_to_resource[resource.reference_name]


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


ANY_WS_PATTERN = re.compile(rf'[{re.escape(ASCII_WHITESPACE)}]+')


def normalize_node_text_string(text: str):
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        # Replace \' with '
        text = text.replace("\\'", "'")

        inner = text[1:-1]
        if not str_needs_whitespace_quotes(inner):
            # No whitespace issues, add \' back
            inner = inner.replace("'", "\\'")
            return inner

        return text

    return ANY_WS_PATTERN.sub(' ', text).strip(ASCII_WHITESPACE)


SKIP_TAGS = {
    'java-symbol',
    'eat-comment',
    'skip',
    'public',
}

PSEUDOLOCALES = (
    'en-rXA',
    'ar-rXB',
    'en-rXC',
)


def parse_xml_resources(
    dir_name: str,
    file_name: str,
    data: bytes,
    resources: Set[Resource],
):
    root = etree.fromstring(data)

    if root.tag != RESOURCES_TAG:
        return None

    comments: List[Comment] = []
    prev_was_comment = False
    index = 0
    for node in root:
        if isinstance(node, Comment):
            # Last element was not a comment, don't stack them
            # Or it was a comment, but they were not stacked
            if (not prev_was_comment) or (
                comments and node_has_space_after(comments[-1])
            ):
                comments = []

            comments.append(node)
            prev_was_comment = True
            continue

        prev_was_comment = False

        tag = node.tag
        if tag in SKIP_TAGS:
            comments = []
            continue

        name = node.attrib.get(NAME_KEY, '')
        if not name:
            raise ValueError('Node has no name')

        product = node.attrib.get(PRODUCT_KEY, '')
        # TODO: find out if this is really correct
        if product == DEFAULT_PRODUCT:
            product = ''

        feature_flag = node.attrib.get(FEATURE_FLAG_KEY, '')

        if node.text is not None:
            # TODO: this is just a hack for wrong @*
            node.text = node.text.replace('@*', '@')

            if tag == DIMEN_TAG:
                node.text = normalize_node_text_dimens_units(node.text)

            if tag == STRING_TAG:
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
            dir_name,
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

        resources.add(resource)


def resources_reference_name_sorted(resources: Set[Resource]):
    return sorted(set(r.reference_name for r in resources))


def sorted_scandir(dir_path: str):
    return sorted(os.scandir(dir_path), key=lambda e: e.path)


@functools.cache
def parse_package_resources_dir(
    res_dir: str,
    parse_all_values: bool,
    read_raw_resources: bool,
):
    resources: Set[Resource] = set()

    for dir_file in sorted_scandir(res_dir):
        if not dir_file.is_dir():
            continue

        dir_name = dir_file.name

        if dir_name.startswith('values-') and any(
            locale in dir_name for locale in PSEUDOLOCALES
        ):
            continue

        is_values = dir_name.startswith('values')
        if is_values and not parse_all_values and dir_name != 'values':
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
            file_name = path.basename(resource_file.path)

            data = None
            if is_values or read_raw_resources:
                with open(resource_file.path, 'rb') as f:
                    data = f.read()

            if is_values:
                assert data is not None
                parse_xml_resources(
                    dir_name,
                    file_name,
                    data,
                    resources,
                )
            else:
                resource = RawResource(
                    dir_name,
                    file_name,
                    data,
                )
                resources.add(resource)

    return resources


def parse_resources(
    resource_map: ResourceMap,
    resources_paths: Iterable[str],
    parse_all_values: bool,
    read_raw_resources: bool,
):
    for resource_path in resources_paths:
        resources = parse_package_resources_dir(
            resource_path,
            parse_all_values,
            read_raw_resources,
        )
        resource_map.add_many(resources)


def parse_overlay_resources(resources_path: str):
    resource_map = ResourceMap(
        by_rel_path=True,
        by_reference_name=True,
        by_references=True,
    )
    parse_resources(
        resource_map,
        [resources_path],
        parse_all_values=True,
        read_raw_resources=True,
    )
    return resource_map


@functools.cache
def get_target_package_resources(
    res_dirs: Tuple[str, ...],
    parse_all_values: bool,
):
    resource_map = ResourceMap(
        by_name=True,
    )
    parse_resources(
        resource_map,
        res_dirs,
        parse_all_values=parse_all_values,
        read_raw_resources=False,
    )
    return resource_map


def find_target_package_resources(
    target_packages: List[Tuple[str, str, List[str]]],
    overlay_resources: ResourceMap,
    parse_all_values: bool,
):
    if len(target_packages) == 1:
        _, module_name, resource_dirs = target_packages[0]
        package_resources = get_target_package_resources(
            tuple(resource_dirs),
            parse_all_values=parse_all_values,
        )
        return package_resources, module_name

    best_matching_resources = None
    best_module_name = None
    best_resources = None

    for _, module_name, resource_dirs in target_packages:
        package_resources = get_target_package_resources(
            tuple(resource_dirs),
            parse_all_values=parse_all_values,
        )

        matching_resources = 0
        for resource in overlay_resources:
            package_resource = package_resources.one_by_name(
                resource.name,
            )
            if package_resource is not None:
                matching_resources += 1

        if (
            best_matching_resources is None
            or matching_resources > best_matching_resources
        ):
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


def keep_referenced_resources_from_removal(
    resources_to_remove: Set[Resource],
    all_resources: ResourceMap,
):
    keep_resources: Set[Resource] = set()

    for resource in resources_to_remove:
        # If there are any resources referenced by this resource which will not
        # get removed, do not remove any of them
        resource_referenced_by = all_resources.resources_referenced_by(resource)
        referenced_in_remove = resource_referenced_by & resources_to_remove
        if len(referenced_in_remove) != len(resource_referenced_by):
            keep_resources.add(resource)
            keep_resources.update(referenced_in_remove)

        # If there are resources referencing this resource which will not get
        # removed, do not remove this resource either
        resources_referencing = all_resources.resources_referencing(resource)
        if not resources_referencing <= resources_to_remove:
            keep_resources.add(resource)

    resources_to_remove -= keep_resources


def overlay_resources_process(
    overlay_resources: ResourceMap,
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
    keep_if_referenced: bool = False,
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

    if keep_if_referenced:
        keep_referenced_resources_from_removal(
            removed_resources,
            overlay_resources,
        )

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

    if is_raw_resource(resource):
        if resource.name in resource_entries:
            return True
        if resource.rel_path in resource_entries:
            return True

        for pattern in resource_entries_wildcards(resource_entries):
            if fnmatch(resource.name, pattern):
                return True
            if fnmatch(resource.rel_path, pattern):
                return True

    elif is_xml_resource(resource):
        if resource.name in resource_entries:
            return True

        for pattern in resource_entries_wildcards(resource_entries):
            if fnmatch(resource.name, pattern):
                return True
    else:
        assert False

    return False


def overlay_resources_remove(
    overlay_resources: ResourceMap,
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


def fixup_resource_attrib(
    resource: XMLResource,
    package_resource: XMLResource,
):
    attrib: Optional[Dict[str | bytes, str | bytes]] = None

    def assign_attrib(name: str):
        nonlocal attrib

        package_attrib = package_resource.element.attrib.get(name)
        if resource.element.attrib.get(name) == package_attrib:
            return False

        if attrib is None:
            attrib = dict(resource.element.attrib)

        if package_attrib is None:
            attrib.pop(name)
        else:
            attrib[name] = package_attrib

        return True

    tag = None
    if resource.tag != package_resource.tag:
        tag = package_resource.tag

    assign_attrib('type')
    assign_attrib('format')

    return tag, attrib


def overlay_resources_remove_missing(
    overlay_resources: ResourceMap,
    package_resources: ResourceMap,
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

        matching_package_resources = package_resources.by_name(
            resource.name,
        )
        for package_resource in matching_package_resources:
            if package_resource.is_default:
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
        keep_if_referenced=True,
    )

    return removed_resources, kept_resources


def package_resource_sort_key(resource: Resource):
    assert is_xml_resource(resource)

    return (
        not resource.comments,
        not resource.is_default,
        bool(resource.product),
        resource.rel_dir_path,
        resource.name,
        tuple(
            (
                # Longest length first
                -len(r.text if r.text is not None else ''),
                # Stable sort across text
                r.text if r.text is not None else '',
            )
            for r in resource.comments
        ),
    )


def overlay_resource_fixup_from_package(
    overlay_resources: ResourceMap,
    package_resources: ResourceMap,
):
    wrong_tag_resources: Set[Tuple[str, str]] = set()

    def fixup_resource_from_package(resource: Resource):
        if not is_xml_resource(resource):
            return

        # Let the logic below place it at the end if a package resource is not
        # found
        index = -1
        comments = None
        file_name = resource.file_name
        tag = None
        attrib = None

        package_resource = None
        matching_package_resources = package_resources.by_name(
            resource.name,
        )
        if matching_package_resources:
            matching_package_resources = sorted(
                matching_package_resources,
                key=package_resource_sort_key,
            )
            package_resource = matching_package_resources[0]

        if package_resource is not None:
            assert isinstance(package_resource, XMLResource)
            tag, attrib = fixup_resource_attrib(resource, package_resource)
            index = package_resource.index
            comments = package_resource.comments
            file_name = package_resource.file_name

        new_resource = resource.copy(
            tag=tag,
            attrib=attrib,
            index=index,
            comments=comments,
            file_name=file_name,
        )

        if tag is not None or attrib is not None:
            wrong_tag_resources.add(
                (
                    resource.reference_name,
                    new_resource.reference_name,
                )
            )

        return resource, new_resource

    overlay_resources_process(
        overlay_resources,
        fixup_resource_from_package,
    )

    return wrong_tag_resources


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


def raw_resource_need_aapt_raw(resource: RawResource):
    if not resource.name.endswith('.xml'):
        return False

    try:
        assert resource.data is not None
        if xml_attrib_matches(resource.data, attrib_needs_aapt_raw):
            return True
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


def write_resources(
    overlay_resources: ResourceMap,
    output_path: str,
    resources_dir: str,
    preserved_prefixes: Optional[Dict[str, bytes]],
):
    if preserved_prefixes is None:
        preserved_prefixes = {}

    aapt_raw_resource = None
    for rel_path, resources in overlay_resources.by_rel_path():
        xml_path = path.join(output_path, resources_dir, rel_path)
        preserved = preserved_prefixes.get(xml_path)

        if not resources:
            continue

        if is_by_rel_path_raw_resources(resources):
            assert len(resources) == 1
            resource = next(iter(resources))

            if aapt_raw_resource is None and raw_resource_need_aapt_raw(
                resource
            ):
                aapt_raw_resource = resource
            write_raw_resource(resource, output_path, resources_dir)
        elif is_by_rel_path_xml_resources(resources):
            sorted_resources = sorted(
                resources,
                key=lambda r: (r.index == -1, r.index, r.name),
            )

            write_xml_resources(
                xml_path,
                sorted_resources,
                preserved_prefix=preserved,
            )
        else:
            assert False

    return aapt_raw_resource


def write_raw_resource(
    resource: RawResource,
    output_path: str,
    resources_dir: str,
):
    raw_path = path.join(output_path, resources_dir, resource.rel_path)
    raw_dir_path = path.dirname(raw_path)
    os.makedirs(raw_dir_path, exist_ok=True)
    with open(raw_path, 'wb') as raw:
        assert resource.data is not None
        raw.write(resource.data)


def read_xml_resources_prefix(
    overlay_resources: ResourceMap,
    output_path: str,
    extra_paths: List[str],
):
    rel_xml_paths: Set[str] = set()

    for rel_path, resources in overlay_resources.by_rel_path():
        if not is_by_rel_path_xml_resources(resources):
            continue

        rel_xml_paths.add(rel_path)

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

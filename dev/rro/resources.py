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
    Generic,
    Iterable,
    List,
    Literal,
    Optional,
    Set,
    Tuple,
    TypeVar,
    Union,
    cast,
)

from lxml import etree

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
    rel_path: str
    reference_name: str

    def __init__(
        self,
        rel_dir_path: str,
        name: str,
    ):
        self.rel_dir_path = rel_dir_path
        self.name = name

    @abstractmethod
    def copy(self, rel_dir_path: Optional[str] = None) -> Resource: ...

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
        data: bytes,
    ):
        super().__init__(rel_dir_path, name)

        self.data = data
        self.__hash_keys = (
            self.rel_dir_path,
            self.name,
            len(self.data),
        )
        self.__hash = hash(self.__hash_keys)
        self.rel_path = f'{self.rel_dir_path}/{self.name}'

        resource_type = strip_rel_dir_qualifiers(self.rel_dir_path)
        resource_name = path.splitext(self.name)[0]
        self.reference_name = f'@{resource_type}/{resource_name}'

    def copy(
        self,
        rel_dir_path: Optional[str] = None,
    ):
        return RawResource(
            rel_dir_path if rel_dir_path is not None else self.rel_dir_path,
            self.name,
            self.data,
        )

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
        super().__init__(rel_dir_path, name)

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
        s += etree.tostring(self.element, encoding='unicode')
        s += '\n'
        return s

    def __eq__(self, other: object):
        if not isinstance(other, XMLResource):
            return False

        return self.__hash_keys == other.__hash_keys

    def __hash__(self) -> int:
        return self.__hash


R = TypeVar('R', bound='Resource')


class ResourceMapTyped(Generic[R]):
    def __init__(
        self,
        resources: Optional[Iterable[R]] = None,
        by_keys: Optional[Dict[Tuple[str, ...], R]] = None,
        by_name: Optional[Dict[str, Set[R]]] = None,
        by_reference_name: Optional[Dict[str, Set[R]]] = None,
        by_rel_path: Optional[Dict[str, Set[R]]] = None,
    ):
        self.__all: Set[R] = set()

        self.__by_keys = by_keys
        self.__by_name = by_name
        self.__by_reference_name = by_reference_name
        self.__by_rel_path = by_rel_path

        if resources:
            self.__add_many(resources)

    def __eq__(self, other: object):
        if not isinstance(other, ResourceMapTyped):
            return NotImplemented

        other = cast(ResourceMapTyped[R], other)
        return self.__all == other.__all

    def __iter__(self):
        return iter(self.__all)

    def __len__(self):
        return len(self.__all)

    def __contains__(self, resource: R):
        return resource in self.__all

    def __and__(self, other: ResourceMapTyped[R]):
        return ResourceMap(self.__all & other.__all)

    def __iand__(self, other: ResourceMapTyped[R]):
        removed = self.__all - other.__all
        self.__discard_many(removed)
        return self

    def __sub__(self, other: ResourceMapTyped[R]):
        return ResourceMap(self.__all - other.__all)

    def __or__(self, other: ResourceMapTyped[R]):
        return ResourceMap(self.__all | other.__all)

    def __index_add(
        self,
        index: Optional[Dict[str, Set[R]]],
        key: str,
        resource: R,
    ):
        if index is None:
            return

        s: Optional[Set[R]] = index.get(key, None)
        if s is None:
            s = set()
            index[key] = s

        s.add(resource)

    def add(self, resource: R):
        self.__all.add(resource)
        if self.__by_keys is not None:
            self.__by_keys[resource.keys] = resource
        self.__index_add(
            self.__by_name,
            resource.name,
            resource,
        )
        self.__index_add(
            self.__by_reference_name,
            resource.reference_name,
            resource,
        )
        self.__index_add(
            self.__by_rel_path,
            resource.rel_path,
            resource,
        )

    def __add_many(self, resources: Iterable[R]):
        for resource in resources:
            self.add(resource)

    def __index_remove(
        self,
        index: Optional[Dict[str, Set[R]]],
        key: str,
        resource: R,
        missing_ok: bool,
    ):
        if index is None:
            return

        s = index.get(key)
        if s is None:
            if missing_ok:
                return
            raise KeyError(key)

        if missing_ok:
            s.discard(resource)
        else:
            s.remove(resource)

        if not s:
            del index[key]

    def __remove(self, resource: R, missing_ok: bool):
        if missing_ok:
            self.__all.discard(resource)
        else:
            self.__all.remove(resource)

        if self.__by_keys is not None:
            if missing_ok:
                self.__by_keys.pop(resource.keys, None)
            else:
                self.__by_keys.pop(resource.keys)

        self.__index_remove(
            self.__by_name,
            resource.name,
            resource,
            missing_ok,
        )
        self.__index_remove(
            self.__by_reference_name,
            resource.reference_name,
            resource,
            missing_ok,
        )
        self.__index_remove(
            self.__by_rel_path,
            resource.rel_path,
            resource,
            missing_ok,
        )

    def remove(self, resource: R):
        self.__remove(resource, missing_ok=False)

    def discard(self, resource: R):
        self.__remove(resource, missing_ok=True)

    def __discard_many(self, resources: Iterable[R]):
        for r in resources:
            self.discard(r)

    def all(self) -> Set[R]:
        return self.__all

    def by_rel_path(self):
        assert self.__by_rel_path is not None
        return self.__by_rel_path.items()

    def by_keys(self, keys: Tuple[str, ...]):
        assert self.__by_keys is not None
        return self.__by_keys.get(keys)

    def by_name(self, name: str):
        assert self.__by_name is not None
        return self.__by_name.get(name, set())

    def by_reference_name(self, reference_name: str):
        assert self.__by_reference_name is not None
        return self.__by_reference_name.get(reference_name, set())

    def one_by_name(self, name: str) -> Optional[R]:
        assert self.__by_name is not None
        s = self.__by_name.get(name)
        if s is None:
            return None

        return next(iter(s))


class ResourceMap:
    def __init__(
        self,
        resources: Optional[Iterable[Resource]] = None,
    ):
        self.__all: ResourceMapTyped[Resource] = ResourceMapTyped(
            by_keys={},
            by_name={},
            by_reference_name={},
        )
        self.__xml: ResourceMapTyped[XMLResource] = ResourceMapTyped(
            by_rel_path={},
        )
        self.__raw: ResourceMapTyped[RawResource] = ResourceMapTyped()

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

    def __and__(self, other: ResourceMap):
        return ResourceMap(self.__all & other.__all)

    def __iand__(self, other: ResourceMap):
        removed = self.__all - other.__all
        self.__discard_many(removed)
        return self

    def __sub__(self, other: ResourceMap):
        return ResourceMap(self.__all - other.__all)

    def __isub__(self, other: ResourceMap):
        self.__discard_many(self.__all & other.__all)
        return self

    def __or__(self, other: ResourceMap):
        return ResourceMap(self.__all | other.__all)

    def __ior__(self, other: ResourceMap):
        self.add_many(other.__all)
        return self

    def copy(self):
        return ResourceMap(self.__all)

    def all(self):
        return self.__all

    def raw(self):
        return self.__raw

    def xml(self):
        return self.__xml

    def add(self, resource: Resource):
        self.__all.add(resource)
        if isinstance(resource, XMLResource):
            self.__xml.add(resource)
        elif isinstance(resource, RawResource):
            self.__raw.add(resource)

    def add_many(self, resources: Iterable[Resource]):
        for resource in resources:
            self.add(resource)

    def discard(self, resource: Resource):
        self.__all.discard(resource)
        if isinstance(resource, XMLResource):
            self.__xml.discard(resource)
        elif isinstance(resource, RawResource):
            self.__raw.discard(resource)

    def remove(self, resource: Resource):
        self.__all.remove(resource)
        if isinstance(resource, XMLResource):
            self.__xml.remove(resource)
        elif isinstance(resource, RawResource):
            self.__raw.remove(resource)

    def __discard_many(self, resources: Iterable[Resource]):
        for r in resources:
            self.discard(r)

    def by_keys(self, keys: Tuple[str, ...]):
        return self.__all.by_keys(keys)

    def by_name(self, name: str):
        return self.__all.by_name(name)

    def by_reference_name(self, reference_name: str):
        return self.__all.by_reference_name(reference_name)

    def one_by_name(self, name: str):
        return self.__all.one_by_name(name)


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
        # Replace non-breaking spaces with normal spaces
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
    resources: Set[Resource],
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

        resources.add(resource)


def resources_reference_name_sorted(resources: Set[Resource]):
    return sorted(set(r.reference_name for r in resources))


def sorted_scandir(dir_path: str):
    return sorted(os.scandir(dir_path), key=lambda e: e.path)


@functools.cache
def parse_package_resources_dir(
    res_dir: str,
):
    resources: Set[Resource] = set()

    for dir_file in sorted_scandir(res_dir):
        if not dir_file.is_dir():
            continue

        pseudolocales = ('en-rXA', 'ar-rXB', 'en-rXC')
        if dir_file.name.startswith('values-') and any(
            locale in dir_file.name for locale in pseudolocales
        ):
            continue

        is_values = dir_file.name.startswith('values')
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
                resources.add(resource)

    return resources


def parse_resources(resources_paths: Iterable[str]):
    resource_map = ResourceMap()

    for resource_path in resources_paths:
        resources = parse_package_resources_dir(resource_path)
        resource_map.add_many(resources)

    return resource_map


def parse_overlay_resources(resources_path: str):
    return parse_resources(
        [resources_path],
    )


@functools.cache
def get_target_package_resources(res_dirs: Tuple[str, ...]):
    return parse_resources(
        res_dirs,
    )


def find_target_package_resources(
    target_packages: List[Tuple[str, str, List[str]]],
    overlay_resources: ResourceMap,
):
    if len(target_packages) == 1:
        _, module_name, resource_dirs = target_packages[0]
        package_resources = get_target_package_resources(
            tuple(resource_dirs),
        )
        return package_resources, module_name

    best_matching_resources = None
    best_module_name = None
    best_resources = None

    for _, module_name, resource_dirs in target_packages:
        package_resources = get_target_package_resources(
            tuple(resource_dirs),
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


def get_referencing_resource(
    overlay_resources: ResourceMap,
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


def keep_referenced_resources_from_removal(
    resources_to_remove: ResourceMap,
    all_resources: ResourceMap,
):
    keep_resources: Set[Resource] = set()

    for resource in all_resources.xml():
        refs = get_resource_element_references(resource.element)
        resource_in = resource in resources_to_remove

        for ref in refs:
            ref_resources = all_resources.by_reference_name(ref)

            for ref_resource in ref_resources:
                reference_in = ref_resource in resources_to_remove

                if resource_in and not reference_in:
                    keep_resources.add(resource)
                elif not resource_in and reference_in:
                    keep_resources.add(ref_resource)

    for resource in keep_resources:
        resources_to_remove.remove(resource)


def resource_to_unqualified_keys(resource: Resource):
    rel_dir_path = resource.rel_dir_path
    stripped_rel_dir_path = strip_rel_dir_qualifiers(rel_dir_path)
    unqualified_resource = resource.copy(rel_dir_path=stripped_rel_dir_path)
    return unqualified_resource.keys


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
        if resource.name in resource_entries:
            return True
        if resource.rel_path in resource_entries:
            return True

        for pattern in resource_entries_wildcards(resource_entries):
            if fnmatch(resource.name, pattern):
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


def overlay_resources_fixup_tag(
    overlay_resources: ResourceMap,
    package_resources: ResourceMap,
):
    wrong_tag_resources: Set[Tuple[str, str]] = set()

    def fixup_resource_tag(resource: Resource):
        if not isinstance(resource, XMLResource):
            return

        package_resource = package_resources.one_by_name(
            resource.name,
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

        package_resource = package_resources.one_by_name(resource.name)
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


def package_resource_sort_key(resource: Resource):
    assert isinstance(resource, XMLResource)

    return (
        not resource.comments,
        '-' in resource.rel_dir_path,
        bool(resource.product),
        resource.rel_dir_path,
        resource.name,
    )


def overlay_resource_fixup_from_package(
    overlay_resources: ResourceMap,
    package_resources: ResourceMap,
):
    def fixup_resource_from_package(resource: Resource):
        if not isinstance(resource, XMLResource):
            return

        # Let the logic below place it at the end if a package resource is not
        # found
        index = -1
        comments = None
        file_name = resource.file_name

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


def remove_identical_resource(
    resource: Resource,
    resources: ResourceMap,
    package_resources: Optional[ResourceMap],
):
    if package_resources is None:
        return

    package_resource = package_resources.by_keys(resource.keys)
    if package_resource is None:
        return

    if resource != package_resource:
        return

    resources.remove(resource)


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


def raw_resources_need_aapt_raw(resources: ResourceMap):
    for resource in resources.raw():
        if not resource.name.endswith('.xml'):
            continue

        try:
            if xml_attrib_matches(resource.data, attrib_needs_aapt_raw):
                return resource
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
    overlay_resources: ResourceMap,
    output_path: str,
    resources_dir: str,
    preserved_prefixes: Optional[Dict[str, bytes]],
):
    if preserved_prefixes is None:
        preserved_prefixes = {}

    for rel_path, resources in overlay_resources.xml().by_rel_path():
        xml_path = path.join(output_path, resources_dir, rel_path)
        preserved = preserved_prefixes.get(xml_path)
        sorted_resources = sorted(
            resources, key=lambda r: (r.index == -1, r.index, r.name)
        )

        write_xml_resources(
            xml_path,
            sorted_resources,
            preserved_prefix=preserved,
        )


def write_overlay_raw_resources(
    overlay_resources: ResourceMap,
    output_path: str,
    resources_dir: str,
):
    for raw_resource in overlay_resources.raw():
        raw_path = path.join(output_path, resources_dir, raw_resource.rel_path)
        raw_dir_path = path.dirname(raw_path)
        os.makedirs(raw_dir_path, exist_ok=True)
        with open(raw_path, 'wb') as raw:
            raw.write(raw_resource.data)


def read_xml_resources_prefix(
    overlay_resources: ResourceMap,
    output_path: str,
    extra_paths: List[str],
):
    rel_xml_paths: Set[str] = set()

    for resource in overlay_resources.xml():
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

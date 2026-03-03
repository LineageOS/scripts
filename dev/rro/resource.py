# SPDX-FileCopyrightText: 2026 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from enum import Enum, auto
from os import path
from typing import Dict, Iterable, List, Optional, Set, Tuple, TypeGuard

from lxml import etree

from rro.utils import get_resource_element_references, strip_dir_name_qualifiers
from utils.frozendict import FrozenDict
from utils.xml_utils import xml_element_canonical_str

Element = etree._Element  # type: ignore
Comment = etree._Comment  # type: ignore


class ResourceType(Enum):
    XML = auto()
    RAW = auto()


class Resource(ABC):
    rel_path: str
    reference_name: str

    def __init__(
        self,
        dir_name: str,
        name: str,
        is_default: bool,
        resource_type: ResourceType,
    ):
        if is_default:
            self.stripped_dir_name = dir_name
        else:
            self.stripped_dir_name = strip_dir_name_qualifiers(dir_name)
        self.dir_name = dir_name
        self.is_default = is_default
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
        dir_name: str,
        name: str,
        is_default: bool,
        data: Optional[bytes],
    ):
        super().__init__(dir_name, name, is_default, ResourceType.RAW)

        self.data = data
        self.__hash_keys = (
            self.dir_name,
            self.name,
            0 if self.data is None else len(self.data),
        )
        self.__hash = hash(self.__hash_keys)
        self.rel_path = f'{self.dir_name}/{self.name}'

        resource_name = path.splitext(self.name)[0]
        self.reference_name = f'@{self.stripped_dir_name}/{resource_name}'

    @property
    def keys(self):
        return (
            self.dir_name,
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
        return f'{self.dir_name}/{self.name}'


class XMLResource(Resource):
    def __init__(
        self,
        index: int,
        res_dir: str,
        file_name: str,
        dir_name: str,
        is_default: bool,
        tag: str,
        name: str,
        element: Element,
        comments: List[Comment],
        product: str,
        feature_flag: str,
    ):
        super().__init__(dir_name, name, is_default, ResourceType.XML)

        self.index = index
        self.tag = tag
        self.res_dir = res_dir
        self.file_name = file_name
        self.element = element
        self.comments = comments
        self.product = product
        self.feature_flag = feature_flag
        self.reference_name = f'@{self.tag}/{self.name}'
        self.__element_str = xml_element_canonical_str(self.element)
        self.__hash_keys = (
            self.dir_name,
            self.tag,
            self.name,
            self.product,
            self.feature_flag,
            self.__element_str,
        )
        self.__hash = hash(self.__hash_keys)
        self.rel_path = f'{self.dir_name}/{self.file_name}'

    def copy(
        self,
        index: Optional[int] = None,
        res_dir: Optional[str] = None,
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
            res_dir if res_dir is not None else self.res_dir,
            file_name if file_name is not None else self.file_name,
            self.dir_name,
            self.is_default,
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
            self.dir_name,
            self.name,
            self.product,
            self.feature_flag,
        )

    def __repr__(self):
        s = f'{self.dir_name}/{self.file_name}:\n'
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
        by_dir_names: bool = False,
        by_reference_name: bool = False,
        by_rel_path: bool = False,
        by_references: bool = False,
    ):
        self.__all: Set[Resource] = set()

        self.__by_dir_names: Optional[Dict[str, Set[str]]] = None
        if by_dir_names:
            self.__by_dir_names = defaultdict(set)

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

    def __add_dir_names(self, resource: Resource):
        assert self.__by_dir_names is not None

        self.__by_dir_names[resource.dir_name].add(resource.name)

        if resource.is_default:
            return

        self.__by_dir_names[resource.stripped_dir_name].add(resource.name)

    def add(self, resource: Resource):
        self.__all.add(resource)
        if self.__by_dir_names is not None:
            self.__add_dir_names(resource)
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
        by_dir_name = self.__by_dir_names
        by_ref = self.__by_reference_name
        by_path = self.__by_rel_path

        for resource in resources:
            if by_dir_name is not None:
                self.__add_dir_names(resource)

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
        assert self.__by_rel_path is not None
        return self.__by_rel_path.items()

    def by_name(self, name: str):
        assert self.__by_name is not None
        return self.__by_name[name]

    def by_reference_name(self, reference_name: str):
        assert self.__by_reference_name is not None
        return self.__by_reference_name[reference_name]

    def one_by_name(self, name: str) -> Optional[Resource]:
        assert self.__by_name is not None
        s = self.__by_name[name]
        if not s:
            return None

        return next(iter(s))

    def __reference_names_to_resource(self, refs: Set[str]):
        resources: Set[Resource] = set()
        for ref in refs:
            resources.update(self.by_reference_name(ref))
        return resources

    def resources_referenced_by(self, resource: Resource):
        assert self.__resource_to_references is not None
        refs = self.__resource_to_references[resource]
        return self.__reference_names_to_resource(refs)

    def resources_referencing(self, resource: Resource):
        assert self.__references_to_resource is not None
        return self.__references_to_resource[resource.reference_name]

    def dir_names_to_names(self):
        assert self.__by_dir_names is not None
        return self.__by_dir_names


def dir_names_to_frozen_dict(dir_names: Dict[str, Set[str]]):
    return FrozenDict({k: frozenset(v) for k, v in dir_names.items()})

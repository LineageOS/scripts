# SPDX-FileCopyrightText: 2026 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum, auto
from os import path
from typing import Dict, List, Optional, Set, Tuple, TypeGuard

from lxml import etree

from rro.utils import strip_dir_name_qualifiers
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

# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from collections import defaultdict
from enum import IntFlag, auto
from typing import (
    Callable,
    DefaultDict,
    Generic,
    Iterable,
    Optional,
    Set,
    TypeVar,
)

from rro.resource import Resource, is_raw_resource, is_xml_resource
from rro.utils import get_resource_element_references
from utils.frozendict import FrozenDict


class IndexFlags(IntFlag):
    ALL = auto()
    BY_NAME = auto()
    BY_REFERENCE_NAME = auto()
    BY_REL_PATH = auto()
    REFERENCES = auto()


class ResourceIndex:
    def add(self, r: Resource) -> None: ...
    def remove(self, r: Resource) -> None: ...


class AllIndex(ResourceIndex):
    def __init__(self):
        self._all: Set[Resource] = set()

    def all(self):
        return self._all

    def add(self, r: Resource):
        self._all.add(r)

    def remove(self, r: Resource):
        self._all.remove(r)

    def copy(self):
        return self._all.copy()

    def __iter__(self):
        return iter(self._all)

    def __len__(self):
        return len(self._all)

    def __contains__(self, r: Resource):
        return r in self._all


K = TypeVar('K')


class KeyToResourcesIndex(Generic[K], ResourceIndex):
    def __init__(self, key_fn: Callable[[Resource], K]):
        self._key_fn = key_fn
        self._m: DefaultDict[K, Set[Resource]] = defaultdict(set)

    def add(self, r: Resource):
        self._m[self._key_fn(r)].add(r)

    def remove(self, r: Resource):
        k = self._key_fn(r)

        s = self._m.get(k)
        if s is None:
            raise KeyError(k)

        s.remove(r)

        if not s:
            del self._m[k]

    def get(self, k: K):
        return self._m[k]

    def items(self):
        return self._m.items()


class RelPathIndex(KeyToResourcesIndex[str]):
    def add(self, r: Resource):
        super().add(r)

        if is_raw_resource(r):
            assert len(self.get(r.rel_path)) == 1, r


class DirNamesIndex(ResourceIndex):
    def __init__(
        self,
        m: Optional[
            DefaultDict[
                # dir name
                str,
                DefaultDict[
                    # resource name
                    str,
                    # count
                    int,
                ],
            ]
        ] = None,
    ):
        if m is None:
            m = defaultdict(lambda: defaultdict(int))

        self._m = m

    def add(self, r: Resource):
        self._m[r.dir_name][r.name] += 1

        if not r.is_default:
            self._m[r.stripped_dir_name][r.name] += 1

    def remove(self, r: Resource):
        self._dec(r.dir_name, r.name)

        if not r.is_default:
            self._dec(r.stripped_dir_name, r.name)

    def _dec(self, dir_name: str, name: str):
        d = self._m.get(dir_name)
        assert d is not None

        c = d.get(name)
        assert c is not None and c > 0

        if c > 1:
            d[name] = c - 1
            return

        d.pop(name)

        if not d:
            self._m.pop(dir_name)

    def dir_names_to_names(self):
        return FrozenDict(
            {dn: frozenset(names.keys()) for dn, names in self._m.items()}
        )


class ReferencesIndex(ResourceIndex):
    def __init__(self):
        self._refs_to_res: DefaultDict[str, Set[Resource]] = defaultdict(set)
        self._res_to_refs: DefaultDict[Resource, Set[str]] = defaultdict(set)

    def add(self, r: Resource):
        if not is_xml_resource(r):
            return

        refs = get_resource_element_references(r.element)

        self._res_to_refs[r].update(refs)

        for ref in refs:
            self._refs_to_res[ref].add(r)

    def remove(self, r: Resource):
        refs = self._res_to_refs.pop(r, None)

        if not refs:
            return

        for ref in refs:
            s = self._refs_to_res.get(ref)

            if not s:
                continue

            s.discard(r)

            if not s:
                del self._refs_to_res[ref]

    def resources_referencing(self, r: Resource):
        return self._refs_to_res[r.reference_name]

    def resources_referenced_by(
        self,
        r: Resource,
        by_ref_index: KeyToResourcesIndex[str],
    ):
        refs = self._res_to_refs.get(r, set())

        out: Set[Resource] = set()

        for ref in refs:
            out.update(by_ref_index.get(ref))

        return out


class ResourceMap:
    def __init__(
        self,
        resources: Optional[Set[Resource]] = None,
        indices: IndexFlags = IndexFlags.ALL,
        dir_names: Optional[DirNamesIndex] = None,
    ):
        self.__indices: list[ResourceIndex] = []

        self.__all = AllIndex()
        self.__indices.append(self.__all)

        self.__by_name: Optional[KeyToResourcesIndex[str]] = None
        self.__by_reference_name: Optional[KeyToResourcesIndex[str]] = None
        self.__by_rel_path: Optional[RelPathIndex] = None
        self.__refs: Optional[ReferencesIndex] = None

        if indices & IndexFlags.BY_NAME:
            self.__by_name = KeyToResourcesIndex(lambda r: r.name)
            self.__indices.append(self.__by_name)

        if indices & IndexFlags.BY_REFERENCE_NAME:
            self.__by_reference_name = KeyToResourcesIndex(
                lambda r: r.reference_name
            )
            self.__indices.append(self.__by_reference_name)

        if indices & IndexFlags.BY_REL_PATH:
            self.__by_rel_path = RelPathIndex(lambda r: r.rel_path)
            self.__indices.append(self.__by_rel_path)

        if indices & IndexFlags.REFERENCES:
            self.__refs = ReferencesIndex()
            self.__indices.append(self.__refs)

        if dir_names is not None:
            self.__dir_names = dir_names
            self.__indices.append(dir_names)

        if resources:
            self.add_many(resources)

    def add(self, r: Resource):
        for idx in self.__indices:
            idx.add(r)

    def add_many(self, resources: Set[Resource]):
        for r in resources:
            for idx in self.__indices:
                idx.add(r)

    def remove(self, r: Resource):
        for idx in self.__indices:
            idx.remove(r)

    def remove_many(self, resources: Iterable[Resource]):
        for r in resources:
            self.remove(r)

    def clear(self):
        self.remove_many(self.__all.copy())

    def __iter__(self):
        return iter(self.__all)

    def __len__(self):
        return len(self.__all)

    def __contains__(self, item: Resource):
        return item in self.__all

    def __eq__(self, other: object):
        if not isinstance(other, ResourceMap):
            return NotImplemented

        return self.__all.all() == other.__all.all()

    def all(self):
        return self.__all.all()

    def by_name(self, name: str):
        assert self.__by_name is not None
        return self.__by_name.get(name)

    def one_by_name(self, name: str):
        assert self.__by_name is not None
        s = self.__by_name.get(name)
        if not s:
            return None
        return next(iter(s))

    def by_reference_name(self, ref: str):
        assert self.__by_reference_name is not None
        return self.__by_reference_name.get(ref)

    def by_rel_path(self):
        assert self.__by_rel_path is not None
        return self.__by_rel_path.items()

    def resources_referencing(self, r: Resource):
        assert self.__refs is not None
        return self.__refs.resources_referencing(r)

    def resources_referenced_by(self, r: Resource):
        assert self.__refs is not None
        assert self.__by_reference_name is not None
        return self.__refs.resources_referenced_by(r, self.__by_reference_name)

    def dir_names_to_names(self):
        return self.__dir_names.dir_names_to_names()


class PackageDirNamesIndex:
    def __init__(self):
        self._m: DefaultDict[
            # package name
            str,
            DefaultDict[
                # dir name
                str,
                DefaultDict[
                    # resource name
                    str,
                    # count
                    int,
                ],
            ],
        ] = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))

    def for_package(self, package: str):
        return DirNamesIndex(self._m[package])

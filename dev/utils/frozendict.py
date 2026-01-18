# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from collections.abc import Iterator, Mapping
from typing import Generic, TypeVar, cast

K = TypeVar('K')
V = TypeVar('V')


class FrozenDict(Mapping[K, V], Generic[K, V]):
    __slots__ = ('__data', '__hash')

    __data: dict[K, V]
    __hash: int

    def __init__(self, data: Mapping[K, V]):
        self.__data = dict(data)
        self.__hash = hash(tuple(sorted(self.__data.items())))

    def __getitem__(self, key: K) -> V:
        return self.__data[key]

    def __contains__(self, key: object) -> bool:
        key = cast(K, key)
        return key in self.__data

    def __iter__(self) -> Iterator[K]:
        return iter(self.__data)

    def __len__(self) -> int:
        return len(self.__data)

    def __hash__(self) -> int:
        return self.__hash

    def __eq__(self, other: object) -> bool:
        if isinstance(other, FrozenDict):
            other = cast(FrozenDict[K, V], other)
            return dict(self.__data) == dict(other)

        return NotImplemented

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self.__data!r})'

# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import itertools
from collections.abc import Hashable
from typing import (
    Dict,
    Generator,
    Generic,
    List,
    Sequence,
    Set,
    Tuple,
    TypeVar,
    Union,
)

T = TypeVar('T')


def tuples_with_nones(
    t: Sequence[Hashable],
    nones_start: int,
) -> Generator[Tuple[Union[Hashable, None], ...], None, None]:
    choices: List[Tuple[Union[Hashable, None], ...]] = []
    for i, x in enumerate(t):
        if i < nones_start:
            choices.append((x,))
        else:
            choices.append((x, None))
    yield from itertools.product(*choices)


class MultiLevelDict(Generic[T]):
    def __init__(self, nones_start: int = 0):
        self.__data: Dict[int, Dict[Tuple[Hashable, ...], Set[T]]] = {}
        self.__all_data: Set[T] = set()
        self.__nones_start = nones_start

    def __len__(self):
        return len(self.__all_data)

    def data(self):
        return self.__data

    def walk(self) -> Generator[T, None, None]:
        yield from self.__all_data

    def add(self, keys: Sequence[Hashable], value: T):
        self.__all_data.add(value)

        levels = len(keys)
        if levels not in self.__data:
            self.__data[levels] = {}

        levels_data = self.__data[levels]

        for t in tuples_with_nones(keys, self.__nones_start):
            if t not in levels_data:
                levels_data[t] = set()

            levels_data[t].add(value)

    def remove(self, keys: Sequence[Hashable], value: T):
        self.__all_data.remove(value)

        levels = len(keys)
        assert levels in self.__data
        levels_data = self.__data[levels]

        for t in tuples_with_nones(keys, self.__nones_start):
            levels_data[t].remove(value)

    def match(
        self,
        keys: Sequence[Hashable],
    ) -> Generator[T]:
        keys_tuple = tuple(keys)

        levels = len(keys_tuple)
        if levels not in self.__data:
            return

        levels_data = self.__data[levels]
        if keys_tuple not in levels_data:
            return

        yield from levels_data[keys_tuple]

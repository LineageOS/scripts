# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import itertools
from collections.abc import Hashable
from typing import (
    Callable,
    Dict,
    Generator,
    Generic,
    Iterable,
    List,
    Sequence,
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
    def __init__(
        self,
        fn: Callable[[T], Tuple[Hashable, ...]],
        nones_start: int = 0,
    ):
        self.__data: Dict[int, Dict[Tuple[Hashable, ...], Dict[T, None]]] = {}
        self.__all_data: Dict[T, None] = {}
        self.__nones_start = nones_start
        self.__fn = fn

    def __len__(self):
        return len(self.__all_data)

    def data(self):
        return self.__data

    def __iter__(self):
        return iter(self.__all_data)

    def add(self, value: T):
        keys = self.__fn(value)
        self.__all_data[value] = None

        levels = len(keys)
        if levels not in self.__data:
            self.__data[levels] = {}

        levels_data = self.__data[levels]

        for t in tuples_with_nones(keys, self.__nones_start):
            if t not in levels_data:
                levels_data[t] = {}

            levels_data[t][value] = None

    def add_many(self, values: Iterable[T]):
        for value in values:
            self.add(value)

    def remove(self, value: T):
        keys = self.__fn(value)
        del self.__all_data[value]

        levels = len(keys)
        assert levels in self.__data
        levels_data = self.__data[levels]

        for t in tuples_with_nones(keys, self.__nones_start):
            del levels_data[t][value]

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

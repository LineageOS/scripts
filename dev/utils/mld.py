# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from collections import defaultdict
from collections.abc import Hashable
from typing import (
    Callable,
    DefaultDict,
    Dict,
    Generic,
    Iterable,
    Iterator,
    List,
    Sequence,
    Tuple,
    TypeVar,
)

T = TypeVar('T')


class MultiLevelDict(Generic[T]):
    def __init__(
        self,
        fn: Callable[[T], Tuple[Hashable, ...]],
        nones_start: int = 0,
    ):
        self.__nones_start = nones_start
        self.__fn = fn

        self.__all_data: Dict[T, Tuple[Hashable, ...]] = {}

        self.__data: DefaultDict[
            # levels
            int,
            DefaultDict[
                # position
                int,
                DefaultDict[
                    # keys
                    Hashable,
                    # values
                    Dict[T, None],
                ],
            ],
        ] = defaultdict(
            lambda: defaultdict(
                lambda: defaultdict(dict),
            ),
        )

    def __len__(self):
        return len(self.__all_data)

    def data(self):
        return self.__data

    def __iter__(self):
        return iter(self.__all_data)

    def add(self, value: T):
        keys = self.__fn(value)

        self.__all_data[value] = keys

        levels = len(keys)
        levels_data = self.__data[levels]

        for i, k in enumerate(keys):
            levels_data[i][k][value] = None

    def add_many(self, values: Iterable[T]):
        for value in values:
            self.add(value)

    def remove(self, value: T):
        keys = self.__fn(value)
        assert self.__all_data[value] == keys

        del self.__all_data[value]

        levels = len(keys)
        levels_data = self.__data[levels]

        for i, key in enumerate(keys):
            position_data = levels_data[i]
            bucket = position_data[key]

            del bucket[value]

            if bucket:
                continue

            del position_data[key]

            if position_data:
                continue

            del levels_data[i]

    def match(self, keys: Sequence[Hashable]) -> Iterator[T]:
        keys = tuple(keys)

        levels = len(keys)
        levels_data = self.__data.get(levels)
        if levels_data is None:
            return

        buckets: List[Dict[T, None]] = []
        saw_not_none = False

        for i, key in enumerate(keys):
            if key is None:
                assert i >= self.__nones_start
                continue

            saw_not_none = True

            position_data = levels_data.get(i)
            if position_data is None:
                return

            bucket = position_data.get(key)
            if bucket is None:
                return

            buckets.append(bucket)

        # Querries that are only None are not allowed
        assert saw_not_none

        buckets.sort(key=len)
        smallest_bucket = buckets[0]
        other_buckets = buckets[1:]

        common = smallest_bucket.keys()
        for bucket in other_buckets:
            common = common & bucket.keys()

        # Keep original order
        for value in smallest_bucket:
            if value in common:
                yield value

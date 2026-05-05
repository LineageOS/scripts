# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from collections import defaultdict
from collections.abc import Hashable
from typing import (
    DefaultDict,
    Dict,
    Iterable,
    Iterator,
    List,
    Optional,
    Sequence,
    Tuple,
)

from sepolicy.rule import Rule


class RuleContainer:
    def __init__(
        self,
        iterable: Optional[Iterable[Rule]] = None,
        sparse_match: bool = False,
    ):
        self.__all_data: Dict[Rule, Tuple[Hashable, ...]] = {}
        self.__sparse_match = sparse_match

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
                    Dict[Rule, None],
                ],
            ],
        ] = defaultdict(
            lambda: defaultdict(
                lambda: defaultdict(dict),
            ),
        )

        if iterable is not None:
            for value in iterable:
                self.add(value)

    def __len__(self):
        return len(self.__all_data)

    def __iter__(self):
        return iter(self.__all_data)

    def __contains__(self, value: Rule):
        return value in self.__all_data

    def add(self, value: Rule):
        keys = value.hash_values
        if value in self.__all_data:
            assert self.__all_data[value] == keys, value
            return

        self.__all_data[value] = keys

        if not self.__sparse_match:
            return

        levels = len(keys)
        levels_data = self.__data[levels]

        for i, k in enumerate(keys):
            levels_data[i][k][value] = None

    def add_many(self, values: Iterable[Rule]):
        for value in values:
            self.add(value)

    def remove(self, value: Rule, optional: bool = False):
        if optional and value not in self.__all_data:
            return False

        keys = value.hash_values

        assert value in self.__all_data, value
        assert self.__all_data[value] == keys, value

        del self.__all_data[value]

        if not self.__sparse_match:
            return

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

        return True

    def remove_many(self, values: Iterable[Rule], optional: bool = False):
        removed_count = 0

        for value in values:
            removed = self.remove(value, optional)
            if removed:
                removed_count += 1

        return removed_count

    def match(self, keys: Sequence[Hashable]) -> Iterator[Rule]:
        assert self.__sparse_match

        levels = len(keys)
        levels_data = self.__data.get(levels)
        if levels_data is None:
            return

        buckets: List[Dict[Rule, None]] = []
        saw_not_none = False

        for i, key in enumerate(keys):
            if key is None:
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

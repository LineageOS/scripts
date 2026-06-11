# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from collections import defaultdict
from collections.abc import Hashable, Set
from typing import (
    DefaultDict,
    Dict,
    Iterable,
    List,
    Optional,
    Sequence,
    Tuple,
    Union,
)

from sepolicy.rule import Rule

MatchIndex = DefaultDict[
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
]


class RuleContainer:
    def __init__(
        self,
        iterable: Optional[Iterable[Rule]] = None,
    ):
        self.__all_data: Dict[Rule, Tuple[Hashable, ...]] = {}
        self.__index: Optional[MatchIndex] = None

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

        existing = self.__all_data.get(value)
        if existing is not None:
            assert existing == keys
            return

        self.__all_data[value] = keys
        self.__index = None

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
        self.__index = None

        return True

    def remove_many(self, values: Iterable[Rule], optional: bool = False):
        removed_count = 0

        for value in values:
            removed = self.remove(value, optional)
            if removed:
                removed_count += 1

        return removed_count

    def __build_index(self):
        self.__index = defaultdict(
            lambda: defaultdict(
                lambda: defaultdict(dict),
            ),
        )

        for value, keys in self.__all_data.items():
            levels_data = self.__index[len(keys)]
            for i, k in enumerate(keys):
                levels_data[i][k][value] = None

        return self.__index

    def match(
        self,
        keys: Sequence[
            Union[
                Hashable,
                Set[Hashable],
                None,
            ],
        ],
    ) -> List[Rule]:
        index = self.__index
        if index is None:
            index = self.__build_index()

        levels = len(keys)
        levels_data = index.get(levels)
        if levels_data is None:
            return []

        buckets: List[Dict[Rule, None]] = []
        saw_not_none = False

        for i, key in enumerate(keys):
            if key is None:
                continue

            saw_not_none = True

            position_data = levels_data.get(i)
            if position_data is None:
                return []

            if isinstance(key, Set):
                merged: Dict[Rule, None] = {}
                for value in key:
                    bucket = position_data.get(value)
                    if bucket is not None:
                        merged.update(bucket)
                if not merged:
                    return []
                buckets.append(merged)
            else:
                bucket = position_data.get(key)
                if bucket is None:
                    return []
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
        values: List[Rule] = []
        for value in smallest_bucket:
            if value in common:
                values.append(value)

        return values

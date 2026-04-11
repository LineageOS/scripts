# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Hashable, List


class ConditionalType:
    def __init__(self, positive: List[str], negative: List[str], is_all: bool):
        self.__positive = positive
        self.__negative = negative
        self.__positive_set = frozenset(positive)
        self.__negative_set = frozenset(negative)
        self.__is_all = is_all
        self.__hash_values = (
            self.__positive_set,
            self.__negative_set,
            is_all,
        )
        self.__hash = hash(self.__hash_values)

    @property
    def hash(self):
        return self.__hash

    @property
    def hash_values(self) -> Hashable:
        return self.__hash_values

    @property
    def positive_set(self):
        return self.__positive_set

    @property
    def negative_set(self):
        return self.__negative_set

    @property
    def positive(self):
        return self.__positive

    @property
    def negative(self):
        return self.__negative

    @property
    def is_all(self):
        return self.__is_all

    def __eq__(self, other: object):
        if not isinstance(other, ConditionalType):
            return False

        if self.__hash != other.hash:
            return False

        return self.__hash_values == other.hash_values

    def __hash__(self):
        return self.__hash

    def __str__(self):
        if self.__is_all:
            return '*'

        s = ''
        if self.__positive:
            s += '{'
            for v in self.__positive:
                s += f' {v}'
            for v in self.__negative:
                s += f' -{v}'
            s += ' }'
        elif len(self.__negative) > 1:
            s += '~'
            s += '{'
            for v in self.__negative:
                s += f' {v}'
            s += ' }'
        else:
            assert len(self.__negative) == 1
            s += '~'
            s += self.__negative[0]

        return s

# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Hashable, List, Set

from utils.utils import Color, color_print


class IConditionalType(ABC):
    @abstractmethod
    def __eq__(self, other: object) -> bool: ...

    @abstractmethod
    def __hash__(self) -> int: ...

    @abstractmethod
    def __str__(self) -> str: ...

    @property
    @abstractmethod
    def hash(self) -> int: ...

    @property
    @abstractmethod
    def hash_values(self) -> Hashable: ...

    @property
    @abstractmethod
    def positive(self) -> List[str]: ...

    @property
    @abstractmethod
    def negative(self) -> List[str]: ...

    @property
    @abstractmethod
    def is_all(self) -> bool: ...


class ConditionalType(IConditionalType):
    def __init__(self, positive: List[str], negative: List[str], is_all: bool):
        self.__positive = positive
        self.__negative = negative
        self.__is_all = is_all
        self.__hash_values = tuple(
            [
                frozenset(positive),
                frozenset(negative),
                is_all,
            ],
        )
        self.__hash = hash(self.__hash_values)

    @property
    def hash(self):
        return self.__hash

    @property
    def hash_values(self) -> Hashable:
        return self.__hash_values

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
        if not isinstance(other, IConditionalType):
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


class ConditionalTypeRedirect(IConditionalType):
    def __init__(self, t: str, m: Dict[str, ConditionalType], i: Set[str]):
        self.__t = t
        self.__m = m
        self.__i = i

    # TODO: is it necessary to do comparisons by actual value, or is it
    # enough to compare the generated type name

    def __get_c(self):
        if self.__t not in self.__m:
            if self.__t not in self.__i:
                color_print(
                    f'Generated type {self.__t} not found',
                    color=Color.YELLOW,
                )
                self.__i.add(self.__t)
            return None

        return self.__m[self.__t]

    @property
    def hash(self):
        c = self.__get_c()
        if c is None:
            assert False
        return c.hash

    @property
    def hash_values(self) -> Hashable:
        c = self.__get_c()
        if c is None:
            assert False
        return c.hash_values

    @property
    def positive(self) -> List[str]:
        c = self.__get_c()
        if c is None:
            return []

        return c.positive

    @property
    def negative(self) -> List[str]:
        c = self.__get_c()
        if c is None:
            return []

        return c.negative

    @property
    def is_all(self):
        c = self.__get_c()
        if c is None:
            return False

        return c.is_all

    def __eq__(self, other: object):
        c = self.__get_c()
        if c is None:
            return self.__t == other

        return c == other

    def __hash__(self):
        c = self.__get_c()
        if c is None:
            return hash(self.__t)

        return hash(c)

    def __str__(self):
        c = self.__get_c()
        if c is None:
            return self.__t

        return str(c)

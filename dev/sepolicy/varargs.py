# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import bisect
from typing import Dict, Iterable, List, Optional, Set, Tuple


def join_varargs(varargs: List[str], force: bool = False):
    s = ' '.join(varargs)

    if force or len(varargs) > 1:
        s = '{ ' + s + ' }'

    return s


def replace_perms(
    perms: List[str],
    class_perms: List[Tuple[str, Set[str]]],
):
    perms_set = set(perms)

    # Perms are sorted by number of rules, no need to find largest one
    for perm, required in class_perms:
        if required <= perms_set:
            remaining = [p for p in perms if p not in required]
            return [perm] + remaining

    return perms


class Perms:
    __ALL = object()

    def __init__(self, values: Iterable[str], is_all: bool):
        self.__values = frozenset(values)
        self.__is_all = is_all
        self.__hash = hash(Perms.__ALL if self.__is_all else self.__values)

    def __contains__(self, value: str):
        if self.__is_all:
            return True

        return value in self.__values

    def __eq__(self, other: object):
        if not isinstance(other, Perms):
            return NotImplemented

        if self.__hash != other.__hash:
            return False

        return (
            self.__is_all == other.__is_all and self.__values == other.__values
        )

    def __hash__(self):
        return self.__hash

    def __le__(self, other: object):
        if not isinstance(other, Perms):
            return NotImplemented

        if other.__is_all:
            return True

        if self.__is_all:
            return False

        return self.__values <= other.__values

    def __is_star(self):
        # fd, property_service are 1-perm, lockdown is 2-perm, avoid replacing
        # them
        return self.__is_all and len(self.__values) > 2

    def format(
        self,
        class_perms: Optional[List[Tuple[str, Set[str]]]],
    ):
        if self.__is_star():
            return '*'

        perms = sorted(self.__values)
        if class_perms is not None:
            perms = replace_perms(
                perms,
                class_perms=class_perms,
            )

        return join_varargs(perms)

    def __str__(self):
        return self.format(
            class_perms=None,
        )


class OrderedPerms:
    def __init__(self, values: Iterable[str]):
        self.__values = tuple(values)
        self.__hash = hash(self.__values)

    def __iter__(self):
        return iter(self.__values)

    def __len__(self):
        return len(self.__values)

    def __eq__(self, other: object):
        if not isinstance(other, OrderedPerms):
            return NotImplemented

        return self.__values == other.__values

    def __hash__(self):
        return self.__hash

    def __str__(self):
        return join_varargs(list(self.__values))


class Types:
    def __init__(self, values: Iterable[str]):
        self.__values = frozenset(values)
        self.__hash = hash(self.__values)

    def __contains__(self, t: str):
        return t in self.__values

    def __eq__(self, other: object):
        if not isinstance(other, Types):
            return NotImplemented

        if self.__hash != other.__hash:
            return False

        return self.__values == other.__values

    def __hash__(self):
        return self.__hash

    def __str__(self):
        values = sorted(self.__values)
        values_str = ', '.join(values)
        return f', {values_str}'


class TypeTransitionTag:
    def __init__(self, value: str):
        self.__value = value
        self.__hash = hash(value)

    def __eq__(self, other: object):
        if not isinstance(other, TypeTransitionTag):
            return NotImplemented

        return self.__value == other.__value

    def __hash__(self):
        return self.__hash

    def __str__(self):
        return self.__value


class Ioctls:
    def __init__(self, ranges: Iterable[Tuple[int, int]]):
        self.__ranges = self._normalize_ranges(ranges)
        self.__ranges_set = frozenset(self.__ranges)
        self.__hash = hash(self.__ranges_set)

    @staticmethod
    def _normalize_ranges(
        ranges: Iterable[Tuple[int, int]],
    ) -> Tuple[Tuple[int, int], ...]:
        merged: List[Tuple[int, int]] = []

        for start, end in sorted(ranges):
            if start > end:
                raise ValueError(f'invalid range: ({start}, {end})')

            if not merged:
                merged.append((start, end))
                continue

            prev_start, prev_end = merged[-1]
            if start <= prev_end + 1:
                merged[-1] = (prev_start, max(prev_end, end))
            else:
                merged.append((start, end))

        return tuple(merged)

    def merge(self, other: Ioctls):
        return Ioctls(self.__ranges + other.__ranges)

    def invert(self, start: int = 0x0000, end: int = 0xFFFF):
        result: List[Tuple[int, int]] = []
        cur = start

        for r_start, r_end in self.__ranges:
            if r_start > cur:
                result.append((cur, r_start - 1))

            cur = r_end + 1
            if cur > end:
                break

        if cur <= end:
            result.append((cur, end))

        return Ioctls(result)

    def __contains__(self, value: int):
        i = bisect.bisect_right(self.__ranges, value, key=lambda t: t[0]) - 1
        if i >= 0:
            start, end = self.__ranges[i]
            return start <= value <= end

        return False

    def __eq__(self, other: object):
        if not isinstance(other, Ioctls):
            return NotImplemented

        if self.__hash != other.__hash:
            return False

        return self.__ranges_set == other.__ranges_set

    def __le__(self, other: Ioctls) -> bool:
        i = j = 0
        a = self.__ranges
        b = other.__ranges

        while i < len(a):
            if j >= len(b):
                return False

            a_start, a_end = a[i]
            b_start, b_end = b[j]

            if a_start < b_start:
                return False

            if a_end <= b_end:
                i += 1
            else:
                j += 1

        return True

    def __sub__(self, other: Ioctls):
        result: List[Tuple[int, int]] = []
        b = other.__ranges
        j = 0

        for a_start, a_end in self.__ranges:
            cur = a_start

            while j < len(b) and b[j][1] < cur:
                j += 1

            k = j
            while k < len(b) and b[k][0] <= a_end:
                b_start, b_end = b[k]

                if b_start > cur:
                    result.append((cur, b_start - 1))

                cur = max(cur, b_end + 1)
                if cur > a_end:
                    break

                k += 1

            if cur <= a_end:
                result.append((cur, a_end))

        return Ioctls(result)

    def __hash__(self):
        return self.__hash

    @classmethod
    def __format_value(
        cls,
        value: int,
        ioctl_defines: Optional[Dict[int, str]],
    ):
        if ioctl_defines is not None and value in ioctl_defines:
            return ioctl_defines[value]
        return hex(value)

    @classmethod
    def __format_range(
        cls,
        start: int,
        end: int,
        ioctl_defines: Optional[Dict[int, str]],
    ):
        start_s = cls.__format_value(start, ioctl_defines)
        if start == end:
            return start_s

        return f'{start_s}-{cls.__format_value(end, ioctl_defines)}'

    def format(
        self,
        ioctls: Optional[List[Tuple[str, Ioctls]]],
        ioctl_defines: Optional[Dict[int, str]],
    ) -> str:
        new_ioctls = self
        inverted = False

        if (
            self.__ranges
            and self.__ranges[0][0] == 0x0000
            and self.__ranges[-1][1] == 0xFFFF
        ):
            inverted = True
            new_ioctls = self.invert()

        parts: List[str] = []
        remaining = new_ioctls

        if ioctls is not None:
            for name, ioctl_ranges in ioctls:
                if ioctl_ranges <= remaining:
                    parts.append(name)
                    remaining = remaining - ioctl_ranges

        # Single ranges need brances too (e.g. 0x89a0-0x89a3)
        has_range = False
        for start, end in remaining.__ranges:
            parts.append(self.__format_range(start, end, ioctl_defines))
            if start != end:
                has_range = True

        s = join_varargs(parts, force=has_range)

        if inverted:
            return f'~{s}'

        return s

    def __str__(self):
        return self.format(
            ioctls=None,
            ioctl_defines=None,
        )

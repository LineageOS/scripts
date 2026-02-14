# SPDX-FileCopyrightText: 2026 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from ctypes import (
    POINTER,
    Structure,
    addressof,
    cast,
    memmove,
    pointer,
    sizeof,
    string_at,
)
from typing import Tuple, TypeVar

T = TypeVar('T', bound=Structure)


def read_struct(
    cls: type[T],
    data: memoryview,
    offset: int = 0,
    size: int = 0,
) -> Tuple[T, int]:
    full = sizeof(cls)
    if size == 0:
        size = full
    else:
        size = min(size, full)

    new_offset = offset + size

    if new_offset > len(data):
        raise ValueError(
            f'Out of bounds: offset={offset:x}, '
            f'new_offset: {new_offset:x}, '
            f'size: {size:x}, '
            f'len: {len(data):x}'
        )

    if size == full:
        return cls.from_buffer_copy(data, offset), new_offset

    data_copy = data[offset:new_offset].tobytes()
    value = cls()
    memmove(addressof(value), data_copy, size)

    return value, new_offset


def cast_struct(dst_cls: type[T], src: Structure) -> T:
    assert sizeof(dst_cls) == sizeof(src)
    return cast(pointer(src), POINTER(dst_cls)).contents


def struct_bytes(data: Structure):
    return string_at(addressof(data), sizeof(data))

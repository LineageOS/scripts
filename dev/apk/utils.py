# SPDX-FileCopyrightText: 2026 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0


import codecs
import struct
from typing import Sequence

_U8 = struct.Struct('<B')
_U16 = struct.Struct('<H')


def read_varlen(data: memoryview, offset: int, unit_size: int):
    assert unit_size in (1, 2), unit_size

    unpack = _U8.unpack_from if unit_size == 1 else _U16.unpack_from
    unit_bits = unit_size * 8
    high_bit_mask = 1 << (unit_bits - 1)

    first = unpack(data, offset)[0]
    offset += unit_size

    if (first & high_bit_mask) == 0:
        return first, offset

    second = unpack(data, offset)[0]
    offset += unit_size

    value = ((first & ~high_bit_mask) << unit_bits) | second

    return value, offset


def read_utf8_string(
    data: memoryview,
    string_start: int,
) -> str:
    _, offset = read_varlen(data, string_start, 1)

    byte_length, offset = read_varlen(
        data,
        offset,
        1,
    )

    string_end = offset + byte_length
    raw_bytes = data[offset:string_end]

    return codecs.decode(raw_bytes, 'utf-8')


def read_utf16_string(
    data: memoryview,
    string_start: int,
) -> str:
    length_in_code_units, offset = read_varlen(
        data,
        string_start,
        2,
    )

    byte_length = length_in_code_units * 2
    string_end = offset + byte_length
    raw_bytes = data[offset:string_end]

    return codecs.decode(raw_bytes, 'utf-16le')


def u16_array_to_str(arr: Sequence[int]) -> str:
    bs = bytes(arr)
    s = bs.decode('utf-16le')
    return s.split('\x00', 1)[0]


def str_from_c(arr: Sequence[int]) -> str:
    return bytes(arr).split(b'\x00', 1)[0].decode('ascii', 'ignore')

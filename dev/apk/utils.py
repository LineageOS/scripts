# SPDX-FileCopyrightText: 2026 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0


from typing import Sequence


def read_varlen(data: memoryview, offset: int, unit_size: int):
    assert unit_size in (1, 2), unit_size

    unit_bits = unit_size * 8
    high_bit_mask = 1 << (unit_bits - 1)

    first = int.from_bytes(data[offset : offset + unit_size], 'little')
    offset += unit_size

    if (first & high_bit_mask) == 0:
        return first, offset

    second = int.from_bytes(data[offset : offset + unit_size], 'little')
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
    raw_bytes = data[offset:string_end].tobytes()

    return raw_bytes.decode('utf-8')


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
    raw_bytes = data[offset:string_end].tobytes()

    return raw_bytes.decode('utf-16le')


def u16_array_to_str(arr: Sequence[int]) -> str:
    bs = bytes(arr)
    s = bs.decode('utf-16le')
    return s.split('\x00', 1)[0]


def str_from_c(arr: Sequence[int]) -> str:
    return bytes(arr).split(b'\x00', 1)[0].decode('ascii', 'ignore')

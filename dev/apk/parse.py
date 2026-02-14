# SPDX-FileCopyrightText: 2026 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from typing import Generator, List, Tuple

from apk.arsc_resources import ARSCAllStyles
from apk.resource_types import (
    RES_STRING_POOL_TYPE,
    ResChunk_header,
    ResStringPool_header,
    ResStringPool_span,
)
from apk.utils import read_utf8_string, read_utf16_string
from utils.struct_utils import read_struct


def iter_child_chunks(
    data: memoryview,
    offset: int,
    end_offset: int,
):
    while offset < end_offset:
        chunk, _ = read_struct(ResChunk_header, data, offset)

        yield offset, chunk
        offset += chunk.size

    assert offset == end_offset


def iter_uint(
    data: memoryview,
    offset: int,
    count: int,
    uint_size: int,
) -> Generator[int, None, None]:
    strings_offsets_size = count * uint_size
    strings_offsets_end = offset + strings_offsets_size
    cut_data = data[offset:strings_offsets_end]

    if uint_size == 2:
        yield from cut_data.cast('H')
    elif uint_size == 4:
        yield from cut_data.cast('I')
    else:
        assert False, uint_size


def iter_offsets(
    offset: int,
    count: int,
    size: int,
):
    for i in range(count):
        yield offset + i * size


def parse_string_pool(data: memoryview, offset: int):
    string_pool_header, _ = read_struct(
        ResStringPool_header,
        data,
        offset,
    )

    assert string_pool_header.header.type == RES_STRING_POOL_TYPE

    is_utf8 = (string_pool_header.flags & ResStringPool_header.UTF8_FLAG) != 0

    string_pool_end = offset + string_pool_header.header.size

    strings_count = string_pool_header.stringCount
    strings_offsets_start = offset + string_pool_header.header.headerSize
    strings_start_offset = offset + string_pool_header.stringsStart

    strings: List[str] = []
    for relative_offset in iter_uint(
        data,
        strings_offsets_start,
        strings_count,
        4,
    ):
        string_offset = strings_start_offset + relative_offset

        if is_utf8:
            value = read_utf8_string(data, string_offset)
        else:
            value = read_utf16_string(data, string_offset)

        strings.append(value)

    styles_count = string_pool_header.styleCount
    styles_offsets_start = strings_offsets_start + strings_count * 4
    styles_start_offset = offset + string_pool_header.stylesStart

    styles: ARSCAllStyles = []
    for relative_offset in iter_uint(
        data,
        styles_offsets_start,
        styles_count,
        4,
    ):
        style_offset = styles_start_offset + relative_offset

        styles_local: List[Tuple[str, int, int]] = []
        while style_offset < string_pool_end:
            style, style_offset = read_struct(
                ResStringPool_span,
                data,
                style_offset,
            )

            assert isinstance(style.name, int)
            assert isinstance(style.firstChar, int)
            assert isinstance(style.lastChar, int)

            if style.name == ResStringPool_span.END:
                break

            styles_local.append(
                (
                    strings[style.name],
                    style.firstChar,
                    style.lastChar,
                )
            )

        styles.append(styles_local)

    assert len(strings) >= len(styles)

    return strings, styles

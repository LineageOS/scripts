from ctypes import Array, Structure, Union, addressof, memmove, sizeof
from typing import Generator, List, Tuple, TypeVar

from apk.arsc_resources import ARSCAllStyles
from apk.resource_types import (
    RES_STRING_POOL_TYPE,
    ResChunk_header,
    ResStringPool_header,
    ResStringPool_span,
)
from apk.utils import read_utf8_string, read_utf16_string

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

    data_copy = data[offset:new_offset].tobytes()
    value = cls()
    memmove(addressof(value), data_copy, size)

    return value, new_offset


def format_value(value: object):
    if isinstance(value, int):
        return f'{value} (0x{value:x})'
    if isinstance(value, bytes):
        return value.hex()

    return repr(value)


def print_struct(
    obj: Structure | Union,
    indent: int = 0,
):
    pad = ' ' * indent
    cls = type(obj)

    kind = ' (union)' if isinstance(obj, Union) else ''
    print(f'{pad}{cls.__name__}{kind} {{')

    for field in obj._fields_:
        field_name = field[0]

        value = getattr(obj, field_name)

        if isinstance(value, (Structure, Union)):
            print(f'{pad}  {field_name}:')
            print_struct(value, indent + 4)
        elif isinstance(value, Array):
            print(f'{pad}  {field_name}: [')
            for item in value:
                if isinstance(item, Structure):
                    print_struct(item, indent + 6)
                else:
                    print(f'{pad}    {format_value(item)}')
            print(f'{pad}  ]')

        else:
            print(f'{pad}  {field_name}: {format_value(value)}')

    print(f'{pad}}}')


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


def parse_string_pool(
    data: memoryview,
    offset: int,
    debug: bool = False,
):
    string_pool_header, _ = read_struct(
        ResStringPool_header,
        data,
        offset,
    )
    if debug:
        print_struct(string_pool_header)

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

    if debug:
        for string in strings:
            print(string)

    return strings, styles

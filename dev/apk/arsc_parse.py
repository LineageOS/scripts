# SPDX-FileCopyrightText: 2026 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

import ctypes
from typing import Dict, List, Optional, Set, Tuple

from apk.arsc_decode import (
    get_resource_by_id,
    get_self_referencing_raw_resource,
)
from apk.arsc_resources import (
    ARSCResourceBag,
    ARSCResourceBagItem,
    ARSCResourcesMap,
    ARSCResourceValue,
    to_resource_id,
)
from apk.parse import (
    iter_child_chunks,
    iter_uint,
    parse_string_pool,
    print_struct,
    read_struct,
)
from apk.resource_types import (
    RES_STRING_POOL_TYPE,
    RES_TABLE_PACKAGE_TYPE,
    RES_TABLE_STAGED_ALIAS_TYPE,
    RES_TABLE_TYPE,
    RES_TABLE_TYPE_SPEC_TYPE,
    RES_TABLE_TYPE_TYPE,
    Res_value,
    ResTable_entry,
    ResTable_header,
    ResTable_map,
    ResTable_map_entry,
    ResTable_package,
    ResTable_sparseTypeEntry,
    ResTable_type,
    ResTable_typeSpec,
)
from apk.utils import u16_array_to_str


def parse_entry_offset(
    table_package: ResTable_package,
    table_type: ResTable_type,
    type_names: List[str],
    key_names: List[str],
    package_name: str,
    data: memoryview,
    entry_offset: int,
    entry_id: int,
    multiplier: int,
    debug: bool,
):
    entry_offset *= multiplier

    entry, _ = read_struct(
        ResTable_entry.Full,
        data,
        entry_offset,
    )

    if entry.flags & ResTable_entry.FLAG_COMPACT:
        assert not (entry.flags & ResTable_entry.FLAG_COMPLEX)

        entry, _ = read_struct(ResTable_entry.Compact, data, entry_offset)
        if debug:
            print_struct(entry)
            print()

        data_type = (entry.flags >> 8) & 0xFF
        entry_data = entry.data

        assert isinstance(table_type.id, int)
        assert isinstance(entry.key, int)

        return ARSCResourceValue(
            package_id=table_package.id,
            type_id=table_type.id,
            entry_id=entry_id,
            key_id=entry.key,
            type_name=type_names[table_type.id - 1],
            key_name=key_names[entry.key],
            package_name=package_name,
            data_type=data_type,
            data=entry_data,
            config=table_type.config,
        )
    elif entry.flags & ResTable_entry.FLAG_COMPLEX:
        entry, _ = read_struct(ResTable_map_entry, data, entry_offset)
        if debug:
            print_struct(entry)

        items: List[ARSCResourceBagItem] = []
        map_entries_offset = entry_offset + entry.size
        for _ in range(entry.count):
            map_entry, map_entries_offset = read_struct(
                ResTable_map,
                data,
                map_entries_offset,
            )
            if debug:
                print_struct(map_entry)

            item = ARSCResourceBagItem(
                resource_id=map_entry.name,
                data_type=map_entry.value.dataType,
                data=map_entry.value.data,
            )
            items.append(item)

        if debug:
            print()

        assert isinstance(table_type.id, int)
        assert isinstance(entry.key, int)

        return ARSCResourceBag(
            package_id=table_package.id,
            type_id=table_type.id,
            entry_id=entry_id,
            key_id=entry.key,
            type_name=type_names[table_type.id - 1],
            key_name=key_names[entry.key],
            package_name=package_name,
            config=table_type.config,
            parent_resource_id=entry.parent,
            items=items,
        )
    else:
        assert not entry.flags

        entry_value_offset = entry_offset + entry.size
        entry_value, _ = read_struct(
            Res_value,
            data,
            entry_value_offset,
        )

        if debug:
            print_struct(entry)
            print_struct(entry_value)
            print()

        data_type = entry_value.dataType
        entry_data = entry_value.data

        assert isinstance(table_type.id, int)
        assert isinstance(entry.key, int)

        return ARSCResourceValue(
            package_id=table_package.id,
            type_id=table_type.id,
            entry_id=entry_id,
            key_id=entry.key,
            type_name=type_names[table_type.id - 1],
            key_name=key_names[entry.key],
            package_name=package_name,
            data_type=data_type,
            data=entry_data,
            config=table_type.config,
        )


def parse_table_type(
    table_package: ResTable_package,
    data: memoryview,
    offset: int,
    size: int,
    resources: ARSCResourcesMap,
    type_names: List[str],
    key_names: List[str],
    package_name: str,
    debug: bool = False,
):
    table_type, _ = read_struct(
        ResTable_type,
        data,
        offset,
        size,
    )
    if debug:
        print_struct(table_type)

    assert table_type.reserved == 0

    is_off16 = table_type.flags & ResTable_type.FLAG_OFFSET16
    is_sparse = table_type.flags & ResTable_type.FLAG_SPARSE
    entries_start_offset = offset + table_type.entriesStart
    entries_data = data[entries_start_offset:]

    if is_sparse:
        entries_offsets_start = offset + table_type.header.headerSize
        entries_offsets_end = offset + table_type.entriesStart
        entries_offsets_size = entries_offsets_end - entries_offsets_start
        entry_size = ctypes.sizeof(ResTable_sparseTypeEntry)
        entries_count = entries_offsets_size // entry_size

        for _ in range(entries_count):
            sparse_type_entry, entries_offsets_start = read_struct(
                ResTable_sparseTypeEntry,
                data,
                entries_offsets_start,
            )
            if debug:
                print_struct(sparse_type_entry)

            resource = parse_entry_offset(
                table_package,
                table_type,
                type_names,
                key_names,
                package_name,
                entries_data,
                sparse_type_entry.offset,
                sparse_type_entry.idx,
                4,
                debug,
            )
            resource_configs_map = resources.setdefault(
                resource.resource_id, {}
            )
            assert resource.resource_id not in resource_configs_map, resource
            resource_configs_map[resource.config_key] = resource
    else:
        offsets_size = 4
        no_entry = ResTable_type.NO_ENTRY
        multiplier = 1
        if is_off16:
            no_entry = ResTable_type.NO_ENTRY16
            offsets_size = 2
            multiplier = 4

        i = 0
        entries_count = table_type.entryCount
        entries_offsets_start = offset + table_type.header.headerSize

        for relative_offset in iter_uint(
            data,
            entries_offsets_start,
            entries_count,
            offsets_size,
        ):
            if relative_offset == no_entry:
                i += 1
                continue

            resource = parse_entry_offset(
                table_package,
                table_type,
                type_names,
                key_names,
                package_name,
                entries_data,
                relative_offset,
                i,
                multiplier,
                debug,
            )
            resource_configs_map = resources.setdefault(
                resource.resource_id, {}
            )
            assert resource.resource_id not in resource_configs_map, resource
            resource_configs_map[resource.config_key] = resource
            i += 1


def parse_table_spec_type(
    table_package: ResTable_package,
    data: memoryview,
    offset: int,
    size: int,
    flags: Dict[int, int],
    debug: bool = False,
):
    table_spec_type, _ = read_struct(
        ResTable_typeSpec,
        data,
        offset,
        size,
    )
    if debug:
        print_struct(table_spec_type)

    package_id = table_package.id
    type_id = table_spec_type.id

    flags_count = table_spec_type.entryCount
    flags_start = offset + table_spec_type.header.headerSize

    entry_id = 0
    for flag in iter_uint(data, flags_start, flags_count, 4):
        resource_id = to_resource_id(package_id, type_id, entry_id)
        entry_id += 1
        assert resource_id not in flags
        flags[resource_id] = flag


def parse_table_package(
    data: memoryview,
    offset: int,
    resources: ARSCResourcesMap,
    flags: Dict[int, int],
    debug: bool = False,
):
    table_package, _ = read_struct(
        ResTable_package,
        data,
        offset,
    )
    if debug:
        print_struct(table_package)

    package_name = u16_array_to_str(table_package.name)
    if debug:
        print(package_name)

    type_pool_chunk_start = offset + table_package.typeStrings
    type_names, _ = parse_string_pool(data, type_pool_chunk_start, debug)

    key_pool_chunk_start = offset + table_package.keyStrings
    key_names, _ = parse_string_pool(data, key_pool_chunk_start, debug)

    package_children_start = offset + table_package.header.headerSize
    package_chunk_end = offset + table_package.header.size

    for chunk_offset, chunk_header in iter_child_chunks(
        data,
        package_children_start,
        package_chunk_end,
    ):
        if chunk_header.type == RES_STRING_POOL_TYPE:
            if chunk_offset in (
                type_pool_chunk_start,
                key_pool_chunk_start,
            ):
                continue

            assert False, chunk_offset
        elif chunk_header.type == RES_TABLE_TYPE_TYPE:
            parse_table_type(
                table_package,
                data,
                chunk_offset,
                chunk_header.headerSize,
                resources,
                type_names,
                key_names,
                package_name,
                debug,
            )
        elif chunk_header.type == RES_TABLE_TYPE_SPEC_TYPE:
            parse_table_spec_type(
                table_package,
                data,
                chunk_offset,
                chunk_header.headerSize,
                flags,
                debug,
            )
            pass
        elif chunk_header.type == RES_TABLE_STAGED_ALIAS_TYPE:
            # TODO: implement
            # print_struct(chunk_header)
            pass
        else:
            print_struct(chunk_header)
            assert False, f'0x{chunk_header.type:x}'


def arsc_parse(data: bytes):
    mm = memoryview(data)
    offset = 0
    debug = False

    table_header, offset = read_struct(
        ResTable_header,
        mm,
        offset,
    )
    if debug:
        print_struct(table_header)

    if table_header.header.type != RES_TABLE_TYPE:
        raise ValueError(
            f'Not a resource table, type: 0x{table_header.header.type:04x}'
        )

    num_res_table_package = 0
    strings: Optional[List[str]] = None
    styles: Optional[List[List[Tuple[str, int, int]]]] = []
    resources: ARSCResourcesMap = {}
    flags: Dict[int, int] = {}

    for chunk_offset, chunk_header in iter_child_chunks(
        mm,
        offset,
        table_header.header.size,
    ):
        if chunk_header.type == RES_STRING_POOL_TYPE:
            strings, styles = parse_string_pool(
                mm,
                chunk_offset,
                debug,
            )
        elif chunk_header.type == RES_TABLE_PACKAGE_TYPE:
            parse_table_package(
                mm,
                chunk_offset,
                resources,
                flags,
                debug,
            )
            num_res_table_package += 1
        else:
            print_struct(chunk_header)
            assert False, f'0x{chunk_header.type:x}'

    assert num_res_table_package == table_header.packageCount
    assert strings is not None

    return strings, styles, resources, flags


def get_resources_referenced_names(
    resources: ARSCResourcesMap,
    strings: List[str],
):
    referenced_names: Set[str] = set()

    for resource_id in sorted(resources.keys()):
        resource = get_resource_by_id(
            resource_id,
            resources,
            None,
        )

        referenced_name = get_self_referencing_raw_resource(
            resource,
            strings,
            resources,
        )
        if referenced_name is not None:
            referenced_names.add(referenced_name)

    return referenced_names

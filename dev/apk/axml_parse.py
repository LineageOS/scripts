# SPDX-FileCopyrightText: 2026 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from typing import List, Optional, Tuple

from apk.arsc_decode import decode_data, stringify_data
from apk.arsc_resources import ARSCResourcesMap
from apk.axml_writer import AXMLWriter
from apk.parse import (
    iter_child_chunks,
    iter_offsets,
    iter_uint,
    parse_string_pool,
    read_struct,
)
from apk.resource_types import (
    RES_STRING_POOL_TYPE,
    RES_XML_CDATA_TYPE,
    RES_XML_END_ELEMENT_TYPE,
    RES_XML_END_NAMESPACE_TYPE,
    RES_XML_FIRST_CHUNK_TYPE,
    RES_XML_LAST_CHUNK_TYPE,
    RES_XML_RESOURCE_MAP_TYPE,
    RES_XML_START_ELEMENT_TYPE,
    RES_XML_START_NAMESPACE_TYPE,
    RES_XML_TYPE,
    ResChunk_header,
    ResXMLTree_attrExt,
    ResXMLTree_attribute,
    ResXMLTree_cdataExt,
    ResXMLTree_endElementExt,
    ResXMLTree_header,
    ResXMLTree_namespaceExt,
    ResXMLTree_node,
)


class AXMLParseError(Exception):
    pass


def decode_string(data: int, strings: List[str]):
    if data == 0xFFFFFFFF:
        return None

    return strings[data]


def parse_resource_map(
    data: memoryview,
    offset: int,
    chunk_header: ResChunk_header,
):
    ids_start = offset + chunk_header.headerSize
    ids_end = offset + chunk_header.size
    ids_count = (ids_end - ids_start) // 4

    resource_ids: List[int] = []
    for resource_id in iter_uint(data, ids_start, ids_count, 4):
        resource_ids.append(resource_id)

    return resource_ids


def resource_id_for_attr(
    attr_name: int,
    resource_ids: Optional[List[int]],
):
    if not resource_ids or attr_name >= len(resource_ids):
        return None

    return resource_ids[attr_name]


def parse_attr(
    data: memoryview,
    offset: int,
    strings: List[str],
    resources: Optional[ARSCResourcesMap],
    reference_resources: Optional[ARSCResourcesMap],
    resource_ids: Optional[List[int]],
):
    attr, _ = read_struct(ResXMLTree_attribute, data, offset)
    attr_uri = decode_string(attr.ns, strings)
    attr_name = decode_string(attr.name, strings) or ''

    attr_data_type = attr.typedValue.dataType
    attr_data = attr.typedValue.data

    resource_id = resource_id_for_attr(attr.name, resource_ids)

    attr_value_str = None
    attr_raw_value = decode_string(attr.rawValue, strings)
    if attr_raw_value is not None:
        attr_value_str = attr_raw_value

    if attr_value_str is None:
        attr_value = decode_data(
            attr_data_type,
            attr_data,
            strings=strings,
            resources=resources,
            reference_resources=reference_resources,
            reference_pacakge_id=0x7F,
            reference_resource_id=resource_id,
        )
        attr_value_str = stringify_data(
            attr_value,
            attr_data_type,
        )

    return (attr_uri, attr_name, attr_value_str)


def parse_xml_node(
    writer: AXMLWriter,
    data: memoryview,
    offset: int,
    strings: List[str],
    resource_ids: Optional[List[int]],
    resources: Optional[ARSCResourcesMap],
    reference_resources: Optional[ARSCResourcesMap],
):
    node, _ = read_struct(
        ResXMLTree_node,
        data,
        offset,
    )
    offset += node.header.headerSize

    if node.header.type in (
        RES_XML_START_NAMESPACE_TYPE,
        RES_XML_END_NAMESPACE_TYPE,
    ):
        ext, _ = read_struct(
            ResXMLTree_namespaceExt,
            data,
            offset,
        )
        prefix = decode_string(ext.prefix, strings) or ''
        uri = decode_string(ext.uri, strings) or ''

        if node.header.type == RES_XML_START_NAMESPACE_TYPE:
            writer.start_namespace(prefix, uri)
        else:
            writer.end_namespace(prefix, uri)

    elif node.header.type == RES_XML_START_ELEMENT_TYPE:
        ext, _ = read_struct(
            ResXMLTree_attrExt,
            data,
            offset,
        )
        elem_uri = decode_string(ext.ns, strings)
        elem_name = decode_string(ext.name, strings) or ''

        attrs: List[Tuple[Optional[str], str, str]] = []
        for attr_offset in iter_offsets(
            offset + ext.attributeStart,
            ext.attributeCount,
            ext.attributeSize,
        ):
            attr = parse_attr(
                data,
                attr_offset,
                strings,
                resources,
                reference_resources,
                resource_ids,
            )

            attrs.append(attr)

        writer.start_element(elem_uri, elem_name, attrs)
    elif node.header.type == RES_XML_END_ELEMENT_TYPE:
        ext, _ = read_struct(
            ResXMLTree_endElementExt,
            data,
            offset,
        )

        writer.end_element()
    elif node.header.type == RES_XML_CDATA_TYPE:
        ext, _ = read_struct(
            ResXMLTree_cdataExt,
            data,
            offset,
        )
        text = decode_string(ext.data, strings) or ''
        writer.text(text)
    else:
        assert False, f'0x{node.header.type:x}'


def axml_parse(
    data: bytes,
    resources: Optional[ARSCResourcesMap],
    reference_resources: Optional[ARSCResourcesMap],
    writer: AXMLWriter,
):
    mm = memoryview(data)
    offset = 0

    xml_header, offset = read_struct(
        ResXMLTree_header,
        mm,
        offset,
    )

    if xml_header.header.type != RES_XML_TYPE:
        raise AXMLParseError(
            f'Not an XML header, type: 0x{xml_header.header.type:04x}'
        )

    writer.start()

    strings: Optional[List[str]] = None
    resource_ids: Optional[List[int]] = None
    for chunk_offset, chunk_header in iter_child_chunks(
        mm,
        offset,
        xml_header.header.size,
    ):
        if chunk_header.type == RES_STRING_POOL_TYPE:
            strings, _ = parse_string_pool(
                mm,
                chunk_offset,
            )
        elif chunk_header.type == RES_XML_RESOURCE_MAP_TYPE:
            resource_ids = parse_resource_map(
                mm,
                chunk_offset,
                chunk_header,
            )
        elif (
            chunk_header.type >= RES_XML_FIRST_CHUNK_TYPE
            and chunk_header.type <= RES_XML_LAST_CHUNK_TYPE
        ):
            assert strings is not None
            parse_xml_node(
                writer,
                mm,
                chunk_offset,
                strings,
                resource_ids,
                resources,
                reference_resources,
            )
        else:
            assert False, f'0x{chunk_header.type:x}'

    writer.finish()

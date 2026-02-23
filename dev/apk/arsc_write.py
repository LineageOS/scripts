# SPDX-FileCopyrightText: 2026 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path
from typing import Dict, List, Set

from apk.arsc_config import decode_config
from apk.arsc_decode import (
    decode_bag_items,
    decode_resource_reference,
    decode_value,
    get_resource_by_id,
    get_self_referencing_raw_resource,
    stringify_data,
)
from apk.arsc_resources import (
    ARSCAllStyles,
    ARSCResource,
    ARSCResourceBag,
    ARSCResourcesMap,
    ARSCResourceValue,
)
from apk.resource_types import (
    Res_value,
    ResTable_config,
    # ResTable_typeSpec
)


def type_name_to_xml_name(type_name: str) -> str:
    if type_name.endswith('array'):
        return 'arrays.xml'

    if type_name.endswith('s'):
        return f'{type_name}.xml'
    return f'{type_name}s.xml'


def group_resources(resources: ARSCResourcesMap):
    grouped_resources: Dict[bytes, Dict[str, List[ARSCResource]]] = {}

    for _, resource_configs_map in resources.items():
        for _, resource in resource_configs_map.items():
            config_resources_map = grouped_resources.setdefault(
                resource.config_key,
                {},
            )
            type_resources_map = config_resources_map.setdefault(
                resource.type_name,
                [],
            )
            type_resources_map.append(resource)

    return grouped_resources


def get_bag_type_name(
    resource: ARSCResourceBag,
    resources: ARSCResourcesMap,
    reference_resources: ARSCResourcesMap,
):
    if not resource.items:
        return None

    data_types: Set[int] = set()
    for item in resource.items:
        if item.data_type != Res_value.TYPE_REFERENCE:
            data_types.add(item.data_type)
            continue

        if item.data in (
            Res_value.DATA_NULL_EMPTY,
            Res_value.DATA_NULL_UNDEFINED,
        ):
            continue

        # TODO: remove this
        found_resource = get_resource_by_id(
            item.data,
            resources,
            reference_resources,
        )

        if (
            isinstance(found_resource, ARSCResourceValue)
            and found_resource.type_name == 'string'
        ):
            data_types.add(Res_value.TYPE_STRING)
            continue

        # TODO: improve
        return None

    if data_types <= set([Res_value.TYPE_STRING]):
        return 'string-array'

    if data_types <= set(
        [
            Res_value.TYPE_INT_DEC,
            Res_value.TYPE_INT_HEX,
            Res_value.TYPE_INT_BOOLEAN,
        ]
    ):
        return 'integer-array'

    return None


def resource_content_to_xml_str(
    resource: ARSCResource,
    strings: List[str],
    styles: ARSCAllStyles,
    resources: ARSCResourcesMap,
    reference_resources: ARSCResourcesMap,
):
    if isinstance(resource, ARSCResourceValue):
        resource_value = decode_value(
            resource,
            strings,
            resources,
            styles=styles,
            reference_resources=reference_resources,
        )

        return stringify_data(resource_value, resource.data_type)
    elif isinstance(resource, ARSCResourceBag):
        item_values = decode_bag_items(
            resource,
            strings,
            styles,
            resources,
            reference_resources,
        )

        item_values_str = ''
        for item_name, item_value in item_values:
            item_name_str = ''
            if item_name is not None:
                item_name_str = f' name="{item_name}"'

            item_values_str += ' ' * 8
            item_values_str += f'<item{item_name_str}>{item_value}</item>\n'

        return item_values_str
    else:
        assert False


def resource_to_xml_str(
    resource: ARSCResource,
    strings: List[str],
    styles: ARSCAllStyles,
    resources: ARSCResourcesMap,
    reference_resources: ARSCResourcesMap,
):
    if (
        get_self_referencing_raw_resource(
            resource,
            strings,
            resources,
        )
        is not None
    ):
        return

    indent = ' ' * 4

    resource_value_str = resource_content_to_xml_str(
        resource,
        strings,
        styles,
        resources,
        reference_resources,
    )

    # TODO: remove apktool compatibility for dimen vs item type="dimen"
    type_name = resource.type_name
    type_str = ''
    if isinstance(resource, ARSCResourceValue):
        if (
            type_name == 'dimen'
            and resource.data_type != Res_value.TYPE_DIMENSION
        ):
            type_name = 'item'
            type_str = ' type="dimen"'
            if resource.data_type == Res_value.TYPE_FLOAT:
                type_str += ' format="float"'

        if type_name == 'raw':
            type_name = 'item'
            type_str = ' type="raw"'

    if isinstance(resource, ARSCResourceBag):
        bag_type_name = get_bag_type_name(
            resource,
            resources,
            reference_resources,
        )
        if bag_type_name is not None:
            type_name = bag_type_name

    parent_str = ''
    if isinstance(resource, ARSCResourceBag) and resource.parent_resource_id:
        parent_reference = decode_resource_reference(
            resource.parent_resource_id,
            sign='@',
            resources=resources,
            reference_resources=reference_resources,
            reference_pacakge_id=resource.package_id,
        )
        parent_str = f' parent="{parent_reference}"'

    end_inline_str = ''
    if not resource_value_str:
        end_inline_str = ' /'

    start_tag_whitespace = ''
    end_tag_whitespace = ''
    if isinstance(resource, ARSCResourceBag) and not end_inline_str:
        start_tag_whitespace = '\n'
        end_tag_whitespace = indent

    resource_str = ''
    resource_str += indent
    resource_str += (
        f'<{type_name}'
        f'{type_str}'
        f' name="{resource.key_name}"'
        f'{parent_str}'
        f'{end_inline_str}'
        f'>'
        f'{start_tag_whitespace}'
    )
    if not end_inline_str:
        resource_str += resource_value_str
        resource_str += f'{end_tag_whitespace}</{type_name}>'
    resource_str += '\n'

    return resource_str


def write_resources(
    strings: List[str],
    styles: ARSCAllStyles,
    resources: ARSCResourcesMap,
    reference_resources: ARSCResourcesMap,
    out_path: Path,
):
    out_path.mkdir(parents=True, exist_ok=True)

    grouped_resources = group_resources(resources)

    for config_key, config_resources_map in grouped_resources.items():
        config = ResTable_config.from_buffer_copy(config_key)
        config_str = decode_config(config)

        values_name = 'values'
        if config_str:
            values_name += f'-{config_str}'

        values_path = Path(out_path, values_name)
        values_path.mkdir(parents=True, exist_ok=True)

        for type_name, type_resources in config_resources_map.items():
            xml_name = type_name_to_xml_name(type_name)
            xml_path = Path(values_path, xml_name)

            resource_strs: List[str] = []
            for resource in type_resources:
                resource_str = resource_to_xml_str(
                    resource,
                    strings,
                    styles,
                    resources,
                    reference_resources,
                )
                if not resource_str:
                    continue

                resource_strs.append(resource_str)

            if not resource_strs:
                continue

            with open(xml_path, 'w') as o:
                o.write('<?xml version="1.0" encoding="utf-8"?>\n')
                o.write('<resources>\n')
                for resource_str in resource_strs:
                    o.write(resource_str)
                o.write('</resources>\n')


def write_resources_public_xml(
    resources: ARSCResourcesMap,
    reference_resources: ARSCResourcesMap,
    flags: Dict[int, int],
    out_path: Path,
):
    values_path = Path(out_path, 'values')
    values_path.mkdir(parents=True, exist_ok=True)
    public_xml_path = Path(values_path, 'public.xml')

    with public_xml_path.open('w', encoding='utf-8') as f:
        f.write('<?xml version="1.0" encoding="utf-8"?>\n')

        if not resources:
            f.write('<resources />\n')
            return

        f.write('<resources>\n')

        # TODO: remove apktool compatibility
        # for resource_id in sorted(flags.keys()):
        #     if not flags[resource_id] & ResTable_typeSpec.SPEC_PUBLIC:
        #         continue
        for resource_id in sorted(resources.keys()):
            resource = get_resource_by_id(
                resource_id,
                resources,
                reference_resources,
            )

            f.write(
                f'    <public type="{resource.type_name}" '
                f'name="{resource.key_name}" '
                f'id="0x{resource_id:08x}" />\n'
            )

        f.write('</resources>\n')

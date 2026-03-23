# SPDX-FileCopyrightText: 2026 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

import math
import struct
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from apk.arsc_decode_string import (
    StringToken,
    decode_string,
    stringify_str,
    stringify_str_tokens,
)
from apk.arsc_resources import (
    ARSCAllStyles,
    ARSCResource,
    ARSCResourceBag,
    ARSCResourcesMap,
    ARSCResourceValue,
)
from apk.resource_types import Res_value, ResTable_map, ResTable_typeSpec

RADIX_MULTS = {
    Res_value.COMPLEX_RADIX_23p0: 1.0,
    Res_value.COMPLEX_RADIX_16p7: 1.0 / (1 << 7),
    Res_value.COMPLEX_RADIX_8p15: 1.0 / (1 << 15),
    Res_value.COMPLEX_RADIX_0p23: 1.0 / (1 << 23),
}
DIMENSION_UNITS = {
    Res_value.COMPLEX_UNIT_PX: 'px',
    # TODO: remove apktool compatibility
    # Res_value.COMPLEX_UNIT_DIP: 'dp',
    Res_value.COMPLEX_UNIT_DIP: 'dip',
    Res_value.COMPLEX_UNIT_SP: 'sp',
    Res_value.COMPLEX_UNIT_PT: 'pt',
    Res_value.COMPLEX_UNIT_IN: 'in',
    Res_value.COMPLEX_UNIT_MM: 'mm',
}
FRACTION_UNITS = {
    Res_value.COMPLEX_UNIT_FRACTION: '%',
    Res_value.COMPLEX_UNIT_FRACTION_PARENT: '%p',
}


def split_resource_id(data: int):
    return (data >> 24) & 0xFF, (data >> 16) & 0xFF, data & 0xFFFF


def is_resource_id_array_item(resource_id: int):
    _, type_id, _ = split_resource_id(resource_id)
    return not type_id


def decode_complex(data: int) -> float:
    mantissa = data >> Res_value.COMPLEX_MANTISSA_SHIFT
    mantissa &= Res_value.COMPLEX_MANTISSA_MASK

    sign_bit = (Res_value.COMPLEX_MANTISSA_MASK + 1) >> 1
    if mantissa & sign_bit:
        mantissa -= Res_value.COMPLEX_MANTISSA_MASK + 1

    radix = data >> Res_value.COMPLEX_RADIX_SHIFT
    radix &= Res_value.COMPLEX_RADIX_MASK

    return mantissa * RADIX_MULTS[radix]


def bits_to_f32(bits: int) -> float:
    return struct.unpack('<f', struct.pack('<I', bits))[0]


def f32_to_bits(value: float) -> int:
    return struct.unpack('<I', struct.pack('<f', float(value)))[0]


def bits_to_int32(value: int) -> int:
    return struct.unpack('<i', struct.pack('<I', value))[0]


def stringify_float(value: float):
    bits = f32_to_bits(value)

    if math.isnan(value):
        return 'NaN'

    if math.isinf(value):
        return '-Infinity' if value < 0 else 'Infinity'

    if value == 0.0:
        return '-0.0' if (bits >> 31) else '0.0'

    xi = int(value)
    if value == float(xi) and abs(xi) < 10**23:
        return f'{xi}.0'

    s = format(value, '.9g')
    for p in range(1, 9):
        ps = format(value, f'.{p}g')
        if f32_to_bits(float(ps)) == bits:
            s = ps
            break

    return s.replace('e', 'E')


def decode_complex_unit(
    data: int,
    table: Dict[int, str],
    multiplier: int = 1,
):
    unit = data >> Res_value.COMPLEX_UNIT_SHIFT
    unit &= Res_value.COMPLEX_UNIT_MASK

    value = decode_complex(data) * multiplier

    return (value, table[unit])


def decode_dimension(data: int):
    return decode_complex_unit(
        data,
        DIMENSION_UNITS,
    )


def decode_fraction(data: int):
    return decode_complex_unit(
        data,
        FRACTION_UNITS,
        multiplier=100,
    )


def stringify_complex(data: Tuple[float, str]):
    return f'{stringify_float(data[0])}{data[1]}'


def get_resource_by_id(
    data: int,
    resources: Optional[ARSCResourcesMap],
    reference_resources: Optional[ARSCResourcesMap],
):
    found_resources = None
    for res in (resources, reference_resources):
        if res is not None and data in res:
            found_resources = res

    assert found_resources is not None

    return next(iter(found_resources[data].values()))


def decode_resource_reference(
    data: int,
    sign: str,
    resources: Optional[ARSCResourcesMap] = None,
    reference_resources: Optional[ARSCResourcesMap] = None,
    reference_flags: Optional[Dict[int, int]] = None,
    reference_package_id: Optional[int] = None,
    package_id_map: Optional[Dict[int, str]] = None,
):
    if data == Res_value.DATA_NULL_UNDEFINED:
        return f'{sign}null'
    elif data == Res_value.DATA_NULL_EMPTY:
        return f'{sign}empty'

    found_resource = get_resource_by_id(
        data,
        resources,
        reference_resources,
    )

    is_public = True
    if (
        reference_resources is not None
        and reference_flags is not None
        and data in reference_resources
        and data in reference_flags
    ):
        is_public = reference_flags[data] & ResTable_typeSpec.SPEC_PUBLIC

    return found_resource.reference_name(
        sign,
        reference_package_id,
        package_id_map,
        is_private=not is_public,
    )


def get_bag_type(resource: ARSCResourceBag):
    for item in resource.items:
        if item.resource_id == ResTable_map.ATTR_TYPE:
            return item.data

    return None


def get_bag_values(
    resource: ARSCResourceBag,
    strings: List[str],
    package_id_map: Optional[Dict[int, str]] = None,
    resources: Optional[ARSCResourcesMap] = None,
    reference_resources: Optional[ARSCResourcesMap] = None,
):
    values: List[Tuple[str, int]] = []
    for item in resource.items:
        if item.resource_id == ResTable_map.ATTR_TYPE:
            continue

        found_resource = get_resource_by_id(
            item.resource_id,
            resources,
            reference_resources,
        )

        item_value = decode_data(
            item.data_type,
            item.data,
            strings,
            package_id_map=package_id_map,
            resources=resources,
            reference_resources=reference_resources,
            reference_package_id=resource.package_id,
        )

        assert isinstance(item_value, int)

        values.append((found_resource.key_name, item_value))

    values.sort(key=lambda i: i[1])

    return values


def decode_attr_flags(value: int, values: List[Tuple[str, int]]):
    flags: List[str] = []

    if not value:
        for flag_name, flag_value in values:
            if not flag_value:
                flags.append(flag_name)

        return flags, value

    for flag_name, flag_value in values:
        if flag_value != value:
            continue

        return [flag_name], value

    value_from_flags = 0
    for flag_name, flag_value in values:
        if (value & flag_value) == flag_value:
            value_from_flags |= flag_value
            flags.append(flag_name)

    return flags, value_from_flags


def decode_attr_flag_str(value: int, values: List[Tuple[str, int]]):
    flags, value_from_flags = decode_attr_flags(value, values)
    if not flags or value_from_flags != value:
        return None

    return '|'.join(flags)


def decode_attr_enum(value: int, values: List[Tuple[str, int]]):
    for flag_name, flag_value in values:
        if value == flag_value:
            return flag_name

    return None


def decode_attr_value(
    data: int,
    reference_resource_id: int,
    strings: List[str],
    package_id_map: Optional[Dict[int, str]] = None,
    resources: Optional[ARSCResourcesMap] = None,
    reference_resources: Optional[ARSCResourcesMap] = None,
):
    found_resource = get_resource_by_id(
        reference_resource_id,
        resources,
        reference_resources,
    )

    if not isinstance(found_resource, ARSCResourceBag):
        return None

    bag_type = get_bag_type(found_resource)
    if bag_type not in (ResTable_map.TYPE_ENUM, ResTable_map.TYPE_FLAGS):
        return None

    bag_values = get_bag_values(
        found_resource,
        strings,
        package_id_map,
        resources,
        reference_resources,
    )

    if bag_type == ResTable_map.TYPE_ENUM:
        return decode_attr_enum(data, bag_values)
    elif bag_type == ResTable_map.TYPE_FLAGS:
        return decode_attr_flag_str(data, bag_values)

    return None


def decode_data(
    data_type: int,
    data: int,
    strings: List[str],
    styles: Optional[ARSCAllStyles] = None,
    package_id_map: Optional[Dict[int, str]] = None,
    resources: Optional[ARSCResourcesMap] = None,
    reference_resources: Optional[ARSCResourcesMap] = None,
    reference_flags: Optional[Dict[int, int]] = None,
    reference_package_id: Optional[int] = None,
    reference_resource_id: Optional[int] = None,
):
    if data_type in (
        Res_value.TYPE_INT_DEC,
        Res_value.TYPE_INT_HEX,
        Res_value.TYPE_INT_BOOLEAN,
    ):
        if data_type == Res_value.TYPE_INT_DEC:
            data = bits_to_int32(data)
        elif data_type == Res_value.TYPE_INT_BOOLEAN:
            data = bool(data)

        if reference_resource_id is not None:
            decoded_data = decode_attr_value(
                data,
                reference_resource_id,
                strings,
                package_id_map,
                resources,
                reference_resources,
            )
            if decoded_data is not None:
                return decoded_data

        return data

    match data_type:
        case Res_value.TYPE_REFERENCE | Res_value.TYPE_DYNAMIC_REFERENCE:
            return decode_resource_reference(
                data,
                sign='@',
                resources=resources,
                reference_resources=reference_resources,
                reference_flags=reference_flags,
                reference_package_id=reference_package_id,
                package_id_map=package_id_map,
            )

        case Res_value.TYPE_ATTRIBUTE | Res_value.TYPE_DYNAMIC_ATTRIBUTE:
            return decode_resource_reference(
                data,
                sign='?',
                resources=resources,
                reference_resources=reference_resources,
                reference_flags=reference_flags,
                reference_package_id=reference_package_id,
                package_id_map=package_id_map,
            )

        case Res_value.TYPE_STRING:
            return decode_string(data, strings, styles)

        case Res_value.TYPE_FLOAT:
            return bits_to_f32(data)

        case Res_value.TYPE_DIMENSION:
            return decode_dimension(data)

        case Res_value.TYPE_FRACTION:
            return decode_fraction(data)

        case Res_value.TYPE_INT_COLOR_ARGB8:
            return f'#{data:08x}'

        case Res_value.TYPE_INT_COLOR_RGB8:
            return f'#{data:06x}'

        case Res_value.TYPE_INT_COLOR_ARGB4:
            return f'#{data:04x}'

        case Res_value.TYPE_INT_COLOR_RGB4:
            return f'#{data:03x}'

        case _:
            assert False, f'{data_type:x}'


def stringify_data(
    data: str | int | bool | float | List[StringToken] | Tuple[float, str],
    data_type: int,
):
    match data_type:
        case Res_value.TYPE_STRING:
            if isinstance(data, str):
                return stringify_str(data)
            elif isinstance(data, list):
                return stringify_str_tokens(data)

            assert False
        case Res_value.TYPE_INT_DEC:
            if isinstance(data, str):
                return data

            return str(data)

        case Res_value.TYPE_INT_HEX:
            if isinstance(data, str):
                return data

            return f'0x{data:08X}'

        case Res_value.TYPE_INT_BOOLEAN:
            if isinstance(data, str):
                return data

            return 'true' if data else 'false'

        case Res_value.TYPE_FLOAT:
            assert isinstance(data, float)
            return stringify_float(data)

        case Res_value.TYPE_DIMENSION:
            assert isinstance(data, tuple)
            return stringify_complex(data)

        case Res_value.TYPE_FRACTION:
            assert isinstance(data, tuple)
            return stringify_complex(data)

        case _:
            pass

    if isinstance(data, str):
        return data

    assert False


def decode_value(
    resource: ARSCResourceValue,
    strings: List[str],
    resources: ARSCResourcesMap,
    styles: Optional[ARSCAllStyles] = None,
    package_id_map: Optional[Dict[int, str]] = None,
    reference_resources: Optional[ARSCResourcesMap] = None,
    reference_flags: Optional[Dict[int, int]] = None,
):
    return decode_data(
        resource.data_type,
        resource.data,
        strings,
        styles=styles,
        package_id_map=package_id_map,
        resources=resources,
        reference_resources=reference_resources,
        reference_flags=reference_flags,
        reference_package_id=resource.package_id,
    )


def decode_bag_items(
    resource: ARSCResourceBag,
    strings: List[str],
    styles: ARSCAllStyles,
    package_id_map: Dict[int, str],
    resources: ARSCResourcesMap,
    reference_resources: ARSCResourcesMap,
    reference_flags: Dict[int, int],
):
    item_values: List[Tuple[Optional[str], str | int | float]] = []

    for item in resource.items:
        is_array = is_resource_id_array_item(item.resource_id)

        reference_resource_id = None
        if not is_array:
            reference_resource_id = item.resource_id

        item_value = decode_data(
            item.data_type,
            item.data,
            strings,
            styles=styles,
            package_id_map=package_id_map,
            resources=resources,
            reference_resources=reference_resources,
            reference_package_id=resource.package_id,
            reference_resource_id=reference_resource_id,
        )
        item_value_str = stringify_data(
            item_value,
            item.data_type,
        )

        item_name = None
        if not is_array:
            item_name = decode_resource_reference(
                item.resource_id,
                sign='',
                resources=resources,
                reference_resources=reference_resources,
                reference_package_id=resource.package_id,
                package_id_map=package_id_map,
            )

        item_values.append((item_name, item_value_str))

    return item_values


def get_self_referencing_raw_resource(
    resource: ARSCResource,
    strings: List[str],
    resources: ARSCResourcesMap,
):
    if not isinstance(resource, ARSCResourceValue):
        return None

    if resource.data_type != Res_value.TYPE_STRING:
        return None

    resource_value = decode_value(
        resource,
        strings,
        resources,
        styles=None,
        reference_resources=None,
    )

    # No styles expected to be applied here
    if not isinstance(resource_value, str):
        return None

    if not resource_value.startswith('res/'):
        return None

    resource_value_path = Path(resource_value)
    if not len(resource_value_path.parts) == 3:
        return None

    if (
        resource.type_name != resource_value_path.parts[1]
        and f'{resource.type_name}-' not in resource_value_path.parts[1]
    ):
        return None

    resource_value_file_name = resource_value_path.stem
    if resource_value_file_name != resource.key_name:
        return None

    return resource_value_file_name

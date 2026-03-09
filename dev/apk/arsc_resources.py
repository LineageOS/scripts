# SPDX-FileCopyrightText: 2026 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from typing import Dict, List, Optional, Tuple

from apk.resource_types import ResTable_config

ARSCResourcesMap = Dict[int, Dict[bytes, 'ARSCResource']]
ARSCStyles = List[Tuple[str, int, int]]
ARSCAllStyles = List[ARSCStyles]


def to_resource_id(package_id: int, type_id: int, entry_id: int):
    return (
        ((package_id & 0xFF) << 24)
        | ((type_id & 0xFF) << 16)
        | (entry_id & 0xFFFF)
    )


class ARSCResource:
    def __init__(
        self,
        package_id: int,
        type_id: int,
        entry_id: int,
        key_id: int,
        type_name: str,
        key_name: str,
        package_name: str,
        config: ResTable_config,
    ):
        self.package_id = package_id
        self.type_id = type_id
        self.entry_id = entry_id
        self.key_id = key_id
        self.type_name = type_name
        self.key_name = key_name
        self.package_name = package_name
        self.config = config
        self.config_key = bytes(config)
        self.resource_id = to_resource_id(package_id, type_id, entry_id)

    def reference_name(
        self,
        sign: str,
        relative_to_package_id: Optional[int] = None,
        package_id_map: Optional[Dict[int, str]] = None,
    ):

        package_str = ''
        if (
            relative_to_package_id is not None
            and relative_to_package_id != self.package_id
            and package_id_map is not None
        ):
            package_str = f'{package_id_map[self.package_id]}:'

        type_str = ''
        if self.type_name != 'attr':
            type_str = f'{self.type_name}/'

        return f'{sign}{package_str}{type_str}{self.key_name}'


class ARSCResourceValue(ARSCResource):
    def __init__(
        self,
        package_id: int,
        type_id: int,
        entry_id: int,
        key_id: int,
        type_name: str,
        key_name: str,
        package_name: str,
        config: ResTable_config,
        data_type: int,
        data: int,
    ):
        super().__init__(
            package_id=package_id,
            type_id=type_id,
            entry_id=entry_id,
            key_id=key_id,
            type_name=type_name,
            key_name=key_name,
            package_name=package_name,
            config=config,
        )
        self.data_type = data_type
        self.data = data

    def __repr__(self):
        return (
            f'{self.__class__.__name__} {{\n'
            f'  package_id: {self.package_id:#04x},\n'
            f'  type_id: {self.type_id:#04x},\n'
            f'  entry_id: {self.entry_id:#06x},\n'
            f'  key_id: {self.key_id},\n'
            f'  type_name: {self.type_name},\n'
            f'  key_name: {self.key_name},\n'
            f'  package_name: {self.package_name},\n'
            f'  resource_id: {self.resource_id:#010x},\n'
            f'  config: {self.config},\n'
            f'  data_type: {self.data_type:#04x},\n'
            f'  data: {self.data:#010x},\n'
            f'}}\n'
        )


class ARSCResourceBagItem:
    def __init__(
        self,
        resource_id: int,
        data_type: int,
        data: int,
    ):
        self.resource_id = resource_id
        self.data_type = data_type
        self.data = data

    def __repr__(self):
        return (
            f'{self.__class__.__name__} {{\n'
            f'  resource_id: {self.resource_id:#010x},\n'
            f'  data_type: {self.data_type:#04x},\n'
            f'  data: {self.data:#010x},\n'
            f'}}\n'
        )


class ARSCResourceBag(ARSCResource):
    def __init__(
        self,
        package_id: int,
        type_id: int,
        entry_id: int,
        key_id: int,
        type_name: str,
        key_name: str,
        package_name: str,
        config: ResTable_config,
        parent_resource_id: int,
        items: List[ARSCResourceBagItem],
    ):
        super().__init__(
            package_id=package_id,
            type_id=type_id,
            entry_id=entry_id,
            key_id=key_id,
            type_name=type_name,
            key_name=key_name,
            package_name=package_name,
            config=config,
        )
        self.parent_resource_id = parent_resource_id
        self.items = items

    def __repr__(self):
        items_repr = ',\n'.join(f'    {repr(item)}' for item in self.items)

        return (
            f'{self.__class__.__name__} {{\n'
            f'  package_id: {self.package_id:#04x},\n'
            f'  type_id: {self.type_id:#04x},\n'
            f'  entry_id: {self.entry_id:#06x},\n'
            f'  key_id: {self.key_id},\n'
            f'  type_name: {self.type_name},\n'
            f'  key_name: {self.key_name},\n'
            f'  package_name: {self.package_name},\n'
            f'  resource_id: {self.resource_id:#010x},\n'
            f'  config: {self.config},\n'
            f'  parent_resource_id: {self.parent_resource_id:#010x},\n'
            f'  items: [\n'
            f'{items_repr}\n'
            f'  ],\n'
            f'}}\n'
        )

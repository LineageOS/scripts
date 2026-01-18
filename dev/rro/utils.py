# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import functools
from typing import Optional, Set

from lxml import etree

Element = etree._Element  # type: ignore


@functools.cache
def strip_dir_name_qualifiers(dir_name: str):
    return dir_name.split('-', maxsplit=1)[0]


def is_referenced_resource_element(
    reference_name: str,
    element: Element,
):
    if element.text is not None and element.text.strip() == reference_name:
        return True

    if element.tail is not None and element.tail.strip() == reference_name:
        return True

    for attrib in element.attrib.values():
        if attrib == reference_name:
            return True

    for child_element in element:
        if is_referenced_resource_element(reference_name, child_element):
            return True

    return False


def get_resource_element_references(
    element: Element,
    referenced_resources: Optional[Set[str]] = None,
):
    if referenced_resources is None:
        referenced_resources = set()

    if element.text is not None:
        element_text = element.text.strip()
        if element_text.startswith('@'):
            referenced_resources.add(element_text)

    if element.tail is not None:
        element_tail = element.tail.strip()
        if element_tail.startswith('@'):
            referenced_resources.add(element_tail)

    for attrib in element.attrib.values():
        assert isinstance(attrib, str)
        if attrib.startswith('@'):
            referenced_resources.add(attrib)

    for child_element in element:
        get_resource_element_references(child_element, referenced_resources)

    return referenced_resources

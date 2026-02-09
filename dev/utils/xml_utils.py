# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Callable, TypeVar

from lxml import etree

Element = etree._Element # type: ignore


def xml_element_canonical_str(element: Element):
    return etree.tostring(element, method='c14n', exclusive=True)


XML_COMMENT_TEXT = """
     SPDX-FileCopyrightText: The LineageOS Project
     SPDX-License-Identifier: Apache-2.0
"""

XML_COMMENT = f"""
<!--{XML_COMMENT_TEXT}-->
"""

T = TypeVar('T', str, bytes)


def xml_attrib_matches(
    xml_data: T,
    match_fn: Callable[[T, T], bool],
):
    tree = etree.fromstring(xml_data)
    for element in tree.iter():
        for attr_name, attr_value in element.attrib.items():
            assert isinstance(attr_name, type(xml_data))
            assert isinstance(attr_value, type(xml_data))
            if match_fn(attr_name, attr_value):
                return True
    return False

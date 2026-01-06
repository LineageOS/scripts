# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Callable

from lxml import etree


def xml_element_canonical_str(element: etree.Element):
    return etree.tostring(element, method='c14n', exclusive=True)


XML_COMMENT_TEXT = """
     SPDX-FileCopyrightText: The LineageOS Project
     SPDX-License-Identifier: Apache-2.0
"""

XML_COMMENT = f"""
<!--{XML_COMMENT_TEXT}-->
"""

def xml_attrib_matches(xml_data: bytes, match_fn: Callable[[str, str], bool]):
    tree = etree.fromstring(xml_data)
    for element in tree.iter():
        for attr_name, attr_value in element.attrib.items():
            if match_fn(attr_name, attr_value):
                return True
    return False

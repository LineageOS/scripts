# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from os import path
from typing import Callable, Optional

from lxml import etree

Element = etree._Element  # type: ignore


def xml_element_canonical_str(element: Element):
    return etree.tostring(element, method='c14n', exclusive=True)


XML_COMMENT_TEXT = """
     SPDX-FileCopyrightText: The LineageOS Project
     SPDX-License-Identifier: Apache-2.0
"""

XML_COMMENT = f"""
<!--{XML_COMMENT_TEXT}-->
"""


def xml_attrib_matches(
    xml_data: str | bytes,
    match_fn: Callable[[str | bytes, str | bytes], bool],
):
    tree = etree.fromstring(xml_data)
    for element in tree.iter():
        for attr_name, attr_value in element.attrib.items():
            if match_fn(attr_name, attr_value):
                return True
    return False


def xml_read_prefix_before_tag(xml_path: str, tag: str) -> Optional[bytes]:
    if not path.exists(xml_path):
        return None

    try:
        with open(xml_path, 'rb') as f:
            data = f.read()
    except Exception:
        return None

    needle = b'<' + tag.encode('utf-8')
    idx = data.find(needle)
    if idx == -1:
        return None

    return data[:idx]

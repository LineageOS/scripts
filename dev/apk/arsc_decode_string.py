# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

import itertools
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple, Union

from apk.arsc_resources import ARSCAllStyles, ARSCStyles


@dataclass(frozen=True)
class StringStartTag:
    tag: str
    attrs: Dict[str, str]


@dataclass(frozen=True)
class StringEndTag:
    tag: str


StringToken = Union[str, StringStartTag, StringEndTag]


def parse_style_name(name: str) -> Tuple[str, Dict[str, str]]:
    parts = name.split(';')
    tag = parts[0]
    attrs: dict[str, str] = {}
    for p in parts[1:]:
        if '=' in p:
            k, v = p.split('=', 1)
            attrs[k] = v
    return tag, attrs


def u16_to_py_indices(value: str, needed: Set[int]) -> Dict[int, int]:
    mapping: Dict[int, int] = {}

    u16_index = 0
    index = 0

    if 0 in needed:
        mapping[0] = 0

    for ch in value:
        u16_units = 1 if ord(ch) <= 0xFFFF else 2
        u16_index += u16_units
        index += 1

        if u16_index in needed:
            mapping[u16_index] = index

    return mapping


def decode_string_with_styles(value: str, styles: ARSCStyles):
    styles = sorted(styles, key=lambda s: (s[1], -(s[2])))

    needed = {0}
    for _, u16_start, u16_end in styles:
        needed.add(u16_start)
        needed.add(u16_end + 1)

    mapping = u16_to_py_indices(value, needed)

    start_tags: Dict[int, List[StringStartTag]] = {}
    end_tags: Dict[int, List[StringEndTag]] = {}

    for tag, u16_start, u16_end in styles:
        start = mapping[u16_start]
        end = mapping[u16_end + 1]

        tag, attrs = parse_style_name(tag)

        start_tag = StringStartTag(tag, attrs)
        start_tags.setdefault(start, []).append(start_tag)

        end_tag = StringEndTag(tag)
        end_tags.setdefault(end, []).append(end_tag)

    boundaries = sorted(
        set(
            itertools.chain(
                [0, len(value)],
                start_tags.keys(),
                end_tags.keys(),
            )
        )
    )

    out: List[StringToken] = []
    last = boundaries[0]
    for pos in boundaries:
        if pos > last:
            out.append(value[last:pos])
            last = pos

        for tag in reversed(end_tags.get(pos, [])):
            out.append(tag)

        for tag in start_tags.get(pos, []):
            out.append(tag)

    return out


def decode_string(
    data: int,
    strings: List[str],
    styles: Optional[ARSCAllStyles] = None,
):
    value = strings[data]
    if styles is None or len(styles) <= data:
        return value

    return decode_string_with_styles(value, styles[data])


def stringify_style_attr(value: str):
    value = value.replace('&', '&amp;')
    value = value.replace('<', '&lt;')
    value = value.replace('>', '&gt;')
    value = value.replace('"', '&quot;')
    return value


ASCII_WHITESPACE = ' \t\n\r\f\v'
NEEDS_QUOTES_PATTERN = re.compile(rf'[{re.escape(ASCII_WHITESPACE)}]{(2,)}')


def str_needs_whitespace_quotes(s: str) -> bool:
    if not s:
        return False

    return (
        s[0] in ASCII_WHITESPACE
        or s[-1] in ASCII_WHITESPACE
        or bool(NEEDS_QUOTES_PATTERN.search(s))
    )


def stringify_str(value: str):
    value = value.replace('&', '&amp;')
    value = value.replace('<', '&lt;')
    # TODO: remove apktool compat
    # value = value.replace('>', '&gt;')

    if not value:
        return value

    needs_quotes = str_needs_whitespace_quotes(value)

    # These would ideally be escaped, but there are some edge cases where it
    # causes issues, like @left or @dp in cutout strings
    # value = value.replace('@', '\\@')
    value = value.replace('\\', '\\\\')
    value = value.replace('?', '\\?')
    value = value.replace('\n', '\\n')
    value = value.replace('\t', '\\t')
    value = value.replace('"', '\\"')

    if not needs_quotes:
        value = value.replace("'", "\\'")

    if needs_quotes:
        return f'"{value}"'

    return value


def stringify_str_tokens(tokens: List[StringToken]) -> str:
    parts: List[str] = []
    for token in tokens:
        if isinstance(token, str):
            parts.append(stringify_str(token))
        elif isinstance(token, StringStartTag):
            if token.attrs:
                attrs = ''.join(
                    f' {k}="{stringify_style_attr(v)}"'
                    for k, v in token.attrs.items()
                )
            else:
                attrs = ''
            parts.append(f'<{token.tag}{attrs}>')
        else:
            parts.append(f'</{token.tag}>')
    return ''.join(parts)

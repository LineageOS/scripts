# SPDX-FileCopyrightText: 2026 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from typing import Dict, List, Optional, Set, TextIO, Tuple


def _esc_attr(v: str) -> str:
    return (
        v.replace('&', '&amp;')
        .replace('"', '&quot;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
    )


def _esc_text(v: str) -> str:
    return v.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


class AXMLWriter:
    def __init__(
        self,
        out: TextIO,
        pretty: bool = True,
        indent: str = ' ' * 4,
        newline: str = '\n',
        skip_space_before_close: Optional[bool] = False,
        sort_attrs: Optional[bool] = False,
        xmlns_first: Optional[bool] = False,
        skip_elements: Optional[Set[str]] = None,
        skip_attrs_by_elem: Optional[
            Dict[str, Set[Tuple[Optional[str], str]]]
        ] = None,
    ):
        self.out = out
        self.pretty = pretty
        self.indent = indent
        self.newline = newline
        self.skip_space_before_close = skip_space_before_close
        self.sort_attrs = sort_attrs
        self.xmlns_first = xmlns_first

        if skip_elements is None:
            skip_elements = set()
        self.skip_elements = skip_elements

        if skip_attrs_by_elem is None:
            skip_attrs_by_elem = {}
        self.skip_attrs_by_elem = skip_attrs_by_elem

        self._skip_depth = 0

        self._ns_stack: List[Tuple[str, str]] = []
        self._uri_to_prefix: Dict[str, str] = {}
        self._pending_xmlns: List[Tuple[str, str]] = []

        self._elem_stack: List[str] = []
        self._depth: int = 0
        self._start_tag_open: bool = False
        self._last_was_text: bool = False

    def _write(self, s: str):
        self.out.write(s)

    def _rebuild_uri_to_prefix(self):
        m: Dict[str, str] = {}
        for p, u in self._ns_stack:
            m[u] = p
        self._uri_to_prefix = m

    def _qname(self, uri: Optional[str], local: str) -> str:
        if not uri:
            return local
        pfx = self._uri_to_prefix.get(uri)
        if pfx:
            return f'{pfx}:{local}'
        return local

    def _ensure_parent_tag_closed(self):
        if self._start_tag_open:
            self._write('>')
            self._start_tag_open = False

    def _maybe_indent(self):
        if not self.pretty:
            return
        if not self._last_was_text:
            self._write(self.newline)
            self._write(self.indent * self._depth)

    def _filter_attrs_for_element(
        self,
        local: str,
        attrs: List[Tuple[Optional[str], str, str]],
    ):
        rules = self.skip_attrs_by_elem.get(local)
        if not rules:
            return attrs

        out: List[Tuple[Optional[str], str, str]] = []
        for a_uri, a_local, a_val in attrs:
            if (a_uri, a_local) in rules:
                continue
            out.append((a_uri, a_local, a_val))

        return out

    def start_namespace(self, prefix: str, uri: str):
        if self._skip_depth > 0:
            return

        prefix = prefix or ''
        self._ns_stack.append((prefix, uri))
        self._rebuild_uri_to_prefix()
        self._pending_xmlns.append((prefix, uri))

    def end_namespace(self, prefix: str, uri: str):
        if self._skip_depth > 0:
            return

        prefix = prefix or ''
        for i in range(len(self._ns_stack) - 1, -1, -1):
            p, u = self._ns_stack[i]
            if p == prefix and u == uri:
                self._ns_stack.pop(i)
                break
        self._rebuild_uri_to_prefix()

    def start_element(
        self,
        uri: Optional[str],
        local: str,
        attrs: List[Tuple[Optional[str], str, str]],
    ):
        if self._skip_depth > 0:
            self._skip_depth += 1
            return

        if local in self.skip_elements:
            self._skip_depth = 1
            return

        attrs = self._filter_attrs_for_element(local, attrs)
        if self.sort_attrs and self._depth != 0:

            def attr_sort_key(item: Tuple[Optional[str], str, str]):
                a_uri, a_local, _ = item
                # Put un-namespaced attrs before android: attrs, then sort by name.
                return (0 if not a_uri and not self.xmlns_first else 1, a_local)

            attrs.sort(key=attr_sort_key)

        self._ensure_parent_tag_closed()
        self._maybe_indent()

        tag = self._qname(uri, local)
        self._write(f'<{tag}')
        self._start_tag_open = True
        self._last_was_text = False

        # TODO: remove apktool compatibility
        is_first_attr = True
        num_attrs = len(self._pending_xmlns) + len(attrs)
        is_single_attr = 1 == num_attrs

        def _write_xmlns():
            nonlocal is_first_attr

            # Emit pending xmlns declarations
            for ns_prefix, ns_uri in self._pending_xmlns:
                # TODO: remove apktool compatibility
                if (not is_first_attr or is_single_attr) and ns_uri.endswith(
                    'android'
                ):
                    self._write(self.newline)
                    self._write(self.indent * self._depth + ' ')

                is_first_attr = False
                self._write(f' xmlns:{ns_prefix}="{_esc_attr(ns_uri)}"')

        if self.xmlns_first:
            _write_xmlns()

        for a_uri, a_local, a_val in attrs:
            is_first_attr = False
            aq = self._qname(a_uri, a_local)
            self._write(f' {aq}="{_esc_attr(a_val)}"')

        if not self.xmlns_first:
            _write_xmlns()

        self._pending_xmlns.clear()

        self._elem_stack.append(tag)
        self._depth += 1

    def end_element(self):
        if self._skip_depth > 0:
            self._skip_depth -= 1
            return

        self._depth -= 1
        tag = self._elem_stack.pop()

        if self._start_tag_open:
            space = ' '
            if self.skip_space_before_close:
                space = ''
            self._write(f'{space}/>')
            self._start_tag_open = False
            self._last_was_text = False
            return

        if self.pretty and not self._last_was_text:
            self._write(self.newline)
            self._write(self.indent * self._depth)

        self._write(f'</{tag}>')
        self._last_was_text = False

    def text(self, s: str):
        if self._skip_depth > 0:
            return

        if not s:
            return

        self._ensure_parent_tag_closed()
        self._write(_esc_text(s))
        self._last_was_text = True

    def start(self):
        self._write('<?xml version="1.0" encoding="utf-8"?>')

    def finish(self):
        assert self._skip_depth == 0

        self._ensure_parent_tag_closed()
        if self.pretty:
            self._write(self.newline)

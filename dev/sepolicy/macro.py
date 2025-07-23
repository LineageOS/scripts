# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import itertools
import re
import subprocess
from functools import partial
from itertools import chain
from pathlib import Path
from typing import Dict, FrozenSet, Generator, List, Optional, Set, Tuple

from sepolicy.classmap import Classmap
from sepolicy.rule import Rule, flatten_parts, unpack_line
from sepolicy.source_rule import SourceRule
from utils.utils import Color, color_print, split_normalize_text

MACRO_START = 'define(`'


def split_macros(lines: List[str]):
    level = 0
    block = ''

    for line in lines:
        assert '#' not in line

        if level == 0 and not line.startswith(MACRO_START):
            continue

        for c in line:
            last_level = level
            if c == '(':
                level += 1
            elif c == ')':
                level -= 1
            elif c == '`':
                level += 1
            elif c == "'":
                level -= 1

            block += c

            if level == 0 and last_level != 0:
                block = block.strip()
                yield block
                block = ''


def _macro_name(macro: str):
    assert macro.startswith(MACRO_START), macro
    assert macro.endswith(')'), macro
    macro = macro[len(MACRO_START) : -1]
    name, body = macro.split("'", 1)

    assert body[0] == ',', body
    body = body[1:]
    body = body.strip()

    return name, body


def macro_name(macro: str):
    return _macro_name(macro)[0]


def macro_name_body(macro: str):
    name, body = _macro_name(macro)

    assert body[0] == '`', body
    assert body[-1] == "'", body
    body = body[1:-1]
    body = body.strip()

    # Squash spaces together
    body = re.sub(r'\s+', ' ', body, flags=re.MULTILINE)

    # Add back newline between rules
    body = re.sub(r'; ', ';\n', body)

    before_strip = body
    body = body.strip()
    assert body == before_strip

    return name, body


ifelse_variable_pattern = re.compile(r'ifelse\s*\(\s*([^,\s\)]+)')
macro_arity_pattern = re.compile(r'\$([1-9][0-9]*)')


def macro_conditionals(body: str):
    return ifelse_variable_pattern.findall(body)


def macro_arity(body: str):
    found_args = macro_arity_pattern.finditer(body)
    used_args = set(int(m.group(1)) for m in found_args)
    return max(used_args) if used_args else 0


def arity_dummy_args(arity: int):
    return ', '.join(f"`${i}'" for i in range(1, arity + 1))


def macro_name_call(macro: str):
    name = macro_name(macro)
    # TODO: move arity outside of this function to be able to use it
    # in other contexts
    # Maybe create a class for each macro?
    arity = macro_arity(macro)
    dummy_args = arity_dummy_args(arity)

    # Define a macro that expands to its expanded definition, quoted
    # Double quote the macro name to prevent its expansion
    return f"`define'(``{name}'', quote_start()\n{name}({dummy_args})\nquote_end())"


def quote_char(c: str):
    change = 'changequote([,])'
    unchange = "changequote(`,')"
    return f'{change}[{change}{c}{unchange}]{unchange}'


def _expand_macro_bodies(
    input_text: str,
    macros: List[str],
    variables: Dict[str, str],
):
    macro_calls = list(map(macro_name_call, macros))

    # Define macros used to change the quote format
    # This is used to add ` and ' around the expanded macro body
    # Macro expansion does not happen when the macro text is
    # quoted more than once
    # Use the standard way of defining macros so that the macro
    # definition functions can be re-used
    input_text += f"""
define(`quote_start', {quote_char('`')})
define(`quote_end', {quote_char("'")})
"""

    # Concatenate all the new macro definition to be able to call m4
    # only once
    input_text += '\n'.join(macro_calls)

    variables_args_k_v = [('-D', f'{k}={v}') for k, v in variables.items()]
    variables_args = [x for p in variables_args_k_v for x in p]
    output_text = subprocess.check_output(
        ['m4', *variables_args],
        input=input_text,
        text=True,
    )

    return output_text


def combine_variable_choices(
    variables: Dict[str, str],
    variables_choices: Dict[str, Tuple[str, ...]],
) -> Generator[Dict[str, str], None, None]:
    # List of (variable_name, value) tuples for each possible value
    # of each variable name
    expanded_choices = [
        [(k, v) for v in vals]
        for k, vals in variables_choices.items()
    ]

    for values in itertools.product(*expanded_choices):
        combined_variables = variables.copy()
        combined_variables.update(dict(values))
        yield combined_variables


def expand_macro_bodies(
    input_text: str,
    macros: List[str],
    variables: Dict[str, str],
    variables_choices: Dict[str, Tuple[str, ...]],
):
    output_text = ''

    for combined_variables in combine_variable_choices(
        variables,
        variables_choices,
    ):
        output_text += _expand_macro_bodies(
            input_text,
            macros,
            combined_variables,
        )

    return output_text


def split_macros_text_name_body(expanded_macros_text: str):
    expanded_macros_lines = split_normalize_text(expanded_macros_text)
    macros = list(split_macros(expanded_macros_lines))
    return list(map(macro_name_body, macros))


def categorize_macros(macros_name_body: List[Tuple[str, str]]):
    expanded_macros: List[Tuple[str, str]] = []
    class_sets: List[Tuple[str, str]] = []
    perms: List[Tuple[str, str]] = []
    ioctls: List[Tuple[str, str]] = []
    ioctl_defines: List[Tuple[str, str]] = []

    empty_macros: Set[str] = set()
    for name, body in macros_name_body:
        if not body:
            if name in empty_macros:
                continue

            color_print(f'Empty macro {name}', color=Color.YELLOW)
            empty_macros.add(name)
            continue

        macro_tuple = (name, body)

        if body.startswith('0x'):
            ioctl_defines.append(macro_tuple)
        elif '_class_set' in name:
            class_sets.append(macro_tuple)
        elif '_perms' in name:
            perms.append(macro_tuple)
        elif '_ioctls' in name:
            ioctls.append(macro_tuple)
        else:
            expanded_macros.append(macro_tuple)

    return expanded_macros, class_sets, perms, ioctls, ioctl_defines


# Extracted from system/sepolicy/build/soong/policy.go
SEPOLICY_FILES = [
    'flagging/flagging_macros',
    'public/global_macros',
    'public/neverallow_macros',
    'public/te_macros',
    'public/ioctl_defines',
    'public/ioctl_macros',
]


def resolve_macro_paths(macro_paths: List[str]):
    macro_file_paths: List[str] = []
    access_vectors_path: Optional[str] = None

    for macro_path in macro_paths:
        mp = Path(macro_path)
        if mp.is_file():
            macro_file_paths.append(str(mp.resolve()))
            continue

        if not mp.is_dir():
            continue

        for file_path in SEPOLICY_FILES:
            fp = Path(macro_path, file_path)
            if fp.is_file():
                macro_file_paths.append(str(fp.resolve()))

        fp = Path(macro_path, 'private/access_vectors')
        if fp.is_file():
            assert access_vectors_path is None
            access_vectors_path = str(fp)

    return macro_file_paths, access_vectors_path


def read_macros(macro_file_paths: List[str]) -> Tuple[str, List[str]]:
    # Join all the macro files
    input_text = ''
    for macro_path in macro_file_paths:
        input_text += Path(macro_path).read_text()
        input_text += '\n'

    # Split into lines, remove empty lines and commented lines
    input_text_lines = split_normalize_text(input_text)
    input_text = ''.join(input_text_lines)

    # After merging all the input files, split them into top-level
    # macro definitions
    # TODO: it's not necessary to process the macros in their entirety,
    # it should be enough to look for define(`(...)',
    macros_text = list(split_macros(input_text_lines))

    return input_text, macros_text


def decompile_macros(
    classmap: Classmap,
    expanded_macros: List[Tuple[str, str]],
):
    from_line_fn = partial(SourceRule.from_line, classmap=classmap)

    expanded_macro_rules: List[Tuple[str, List[Rule]]] = []
    unqiue_macro_rules: Set[Tuple[str, FrozenSet[Rule]]] = set()
    invalid_macro_names: Set[str] = set()
    macro_names: Set[str] = set()
    for name, body in expanded_macros:
        lines = body.splitlines()

        try:
            rules = list(chain.from_iterable(map(from_line_fn, lines)))
        except ValueError:
            invalid_macro_names.add(name)
            continue

        hashable_macro_rule = (name, frozenset(rules))
        if hashable_macro_rule in unqiue_macro_rules:
            continue

        if name in macro_names:
            print(f'Macro {name} has multiple variants')

        expanded_macro_rules.append((name, rules))
        unqiue_macro_rules.add(hashable_macro_rule)
        macro_names.add(name)

    for name in invalid_macro_names:
        color_print(f'Invalid macro {name}', color=Color.YELLOW)

    return expanded_macro_rules


def decompile_perms(perms: List[Tuple[str, str]]):
    decompiled_perms: List[Tuple[str, Set[str]]] = []

    for name, text in perms:
        parts = unpack_line(
            text,
            '{',
            '}',
            ' ',
            open_by_default=True,
            ignored_chars=';',
        )
        parts_set = set(flatten_parts(parts))
        decompiled_perms.append((name, parts_set))

    # Prioritize replacement of largest perm macros
    decompiled_perms.sort(key=lambda np: len(np[1]), reverse=True)

    return decompiled_perms


def unpack_ioctl(part: str):
    if '-' not in part:
        yield hex(int(part, base=16))
        return

    parts = part.split('-')
    assert len(parts) == 2

    start_ioctl = int(parts[0], base=16)
    end_ioctl = int(parts[1], base=16)

    for n in range(start_ioctl, end_ioctl + 1):
        yield hex(n)


def decompile_ioctls(ioctls: List[Tuple[str, str]]):
    decompiled_ioctls: List[Tuple[str, Set[str]]] = []

    for name, text in ioctls:
        parts = unpack_line(
            text,
            '{',
            '}',
            ' ',
            open_by_default=True,
            ignored_chars=';',
        )
        flattened_parts = flatten_parts(parts)
        unpacked_ioctls = map(unpack_ioctl, flattened_parts)
        parts_set = set(chain.from_iterable(unpacked_ioctls))
        decompiled_ioctls.append((name, parts_set))

    return decompiled_ioctls


def decompile_ioctl_defines(ioctl_defines: List[Tuple[str, str]]):
    decompiled_ioctl_defines: Dict[str, str] = {}

    duplicate_ioctls: Set[str] = set()
    for name, text in ioctl_defines:
        value = hex(int(text, base=16))
        if value not in decompiled_ioctl_defines:
            decompiled_ioctl_defines[value] = name
            continue

        if name == decompiled_ioctl_defines[value]:
            continue

        if value in duplicate_ioctls:
            continue

        existing_name = decompiled_ioctl_defines[value]
        color_print(
            f'Ioctl {name}={value} already defined as {existing_name}',
            color=Color.YELLOW,
        )
        duplicate_ioctls.add(value)

    return decompiled_ioctl_defines

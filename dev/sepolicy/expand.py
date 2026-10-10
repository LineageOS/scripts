# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import functools
import re
import subprocess
from pathlib import Path
from typing import (
    Callable,
    Iterable,
    List,
    Optional,
    TypeVar,
)

from sepolicy.macro import (
    ARG_ELSE_MARKER,
    ARG_END_MARKER,
    ARG_IFELSE_MARKER,
    macro_arity,
    macro_name,
)
from utils.frozendict import FrozenDict


@functools.cache
def arity_dummy_args(arity: int):
    return ', '.join(f"`${i}'" for i in range(1, arity + 1))


def macro_dummy_call(name: str, arity: int):
    dummy_args = arity_dummy_args(arity)

    # Define a macro that expands to its expanded definition, quoted
    # Double quote the macro name to prevent its expansion
    return f"`define'(``{name}'', quote(`\n{name}({dummy_args})\n'))\n"


def quote_char(c: str):
    change = 'changequote([,])'
    unchange = "changequote(`,')"
    return f'{change}[{change}{c}{unchange}]{unchange}'


# An ifelse() comparing a macro argument cannot be evaluated while macros are
# expanded with placeholder arguments. Emit both branches between markers.
ARG_IFELSE_DEFINITIONS = f"""
define(`arg_ifelse', `ifelse(substr(`$1', 0, 1), `$', `arg_ifelse_branches(`$1', `$2', `$3', `$4')', `ifelse(`$1', `$2', `$3', `$4')')')
define(`arg_ifelse_branches', `
{ARG_IFELSE_MARKER} $1 $2
$3
{ARG_ELSE_MARKER}
$4
{ARG_END_MARKER}
')
"""

arg_ifelse_pattern = re.compile(r'\bifelse\((?=\$[1-9])')


def expand_macro_calls(
    texts: Iterable[str],
    environment_texts: List[str],
    variables: FrozenDict[str, str],
    preserve_macros: bool,
    text_name: str,
    verbose: bool,
):
    input_text = ''

    # Define macros used to change the quote format
    # This is used to add ` and ' around the expanded macro body
    # Macro expansion does not happen when the macro text is
    # quoted more than once
    # Use the standard way of defining macros so that the macro
    # definition functions can be re-used
    input_text += f"""
define(`quote_start', {quote_char('`')})
define(`quote_end', {quote_char("'")})
define(`quote', `quote_start()`'$1`'quote_end()')
"""

    # Noop out divert() to get all the output
    input_text += """
define(`divert', `')
"""

    text_parts: List[str] = []
    if preserve_macros:
        input_text += ARG_IFELSE_DEFINITIONS
        texts = [arg_ifelse_pattern.sub('arg_ifelse(', t) for t in texts]

        for text in texts:
            name = macro_name(text)
            if name is None:
                continue

            arity = macro_arity(text)
            dummy_call = macro_dummy_call(name, arity)
            text_parts.append(dummy_call)
            text_parts.append('\n')

    input_text += '\n'.join(
        [
            *environment_texts,
            *texts,
            *text_parts,
        ]
    )

    if verbose:
        text_path = Path(f'/tmp/m4/input_macro_{text_name}.txt')
        text_path.parent.mkdir(exist_ok=True)
        print(f'Writing {text_path}')
        text_path.write_text(input_text)

    arguments: List[str] = []
    for key, value in variables.items():
        arguments.extend(['-D', f'{key}={value}'])

    output_text = subprocess.check_output(
        ['m4', '-E', *arguments],
        input=input_text,
        text=True,
    )

    if verbose:
        text_path = Path(f'/tmp/m4/output_macro_{text_name}.txt')
        print(f'Writing {text_path}')
        text_path.write_text(output_text)

    return output_text


T = TypeVar('T')


def expand_macro_calls_and_split(
    texts: List[str],
    environment_texts: List[str],
    variables: FrozenDict[str, str],
    split_fn: Callable[[str], List[str]],
    map_fn: Callable[[str], Optional[T]],
    preserve_macros: bool,
    text_name: str,
    verbose: bool,
):
    text = '\n'.join(texts)

    if preserve_macros:
        split_texts = split_fn(text)
    else:
        split_texts = [text]

    expanded_text = expand_macro_calls(
        split_texts,
        environment_texts,
        variables,
        preserve_macros,
        text_name,
        verbose,
    )

    mapped = map(map_fn, split_fn(expanded_text))
    return [value for value in mapped if value is not None]

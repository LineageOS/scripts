# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import itertools
import re
import subprocess
from dataclasses import dataclass, field
from functools import cache, partial
from itertools import chain
from pathlib import Path
from typing import (
    Dict,
    FrozenSet,
    Generator,
    Iterable,
    List,
    Optional,
    Set,
    Tuple,
)

from sepolicy.classmap import Classmap
from sepolicy.rule import Rule, flatten_parts, unpack_line
from sepolicy.rules import split_rules
from sepolicy.source_rule import SourceRule, format_ioctl_str, unpack_ioctls
from utils.utils import Color, color_print, split_normalize_text

TARGET_FLAG_PREFIX = 'target_flag_'
MACRO_START = 'define(`'
BUILTIN_CALLS = set(['define', 'ifelse', 'eval'])
HANDLED_VARIABLE_MACRO_IFELSE = set(
    [
        # TODO: implement this properly by allowing macros to have conditional
        # rules based on input params
        ('domain_trans', '$1'),
        ('is_flag_enabled', 'target_flag_$1'),
        ('is_flag_disabled', 'target_flag_$1'),
    ],
)


def split_macros(lines: List[str]):
    for block in split_rules(lines):
        if not block.startswith(MACRO_START):
            color_print(
                f'Skipping non-macro block: {block}',
                color=Color.YELLOW,
            )
            continue

        assert block.endswith(')'), block
        yield block


def macro_name_body_raw(macro: str):
    if not macro.startswith(MACRO_START):
        return None, macro

    assert macro.startswith(MACRO_START), macro
    assert macro.endswith(')'), macro
    macro = macro[len(MACRO_START) : -1]
    name, body = macro.split("'", 1)

    assert body[0] == ',', body
    body = body[1:]
    body = body.strip()

    return name, body


def macro_is_unquoted_ifelse(body: str):
    return body.startswith('ifelse(')


def macro_name(macro: str):
    return macro_name_body_raw(macro)[0]


def macro_name_body(macro: str):
    name, body = macro_name_body_raw(macro)

    # Only macros are quote-delimited, free-standing rules are not
    if name is not None:
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


ifelse_arg_variable_pattern = re.compile(
    r"\bifelse\s*\(\s*([^,\s\)]+)\s*,\s*`([^']*)'",
)
is_flag_enabled_regex = re.compile(
    r'\bis_flag_enabled\s*\(\s*([^\s,)]+)',
)
macro_call_pattern = re.compile(r'\b([A-Za-z_][A-Za-z0-9_]*)\s*\(')
macro_arity_pattern = re.compile(r'\$([1-9][0-9]*)')


def macro_used_variables(name: Optional[str], body: str):
    # TODO: handle is_flag_enabled
    #
    # TODO: this only uses ifelse() statements to determine the used variables
    # but some variables might be used outside of that, like
    # starting_at_board_api(), which uses target_board_api_level inside an eval
    # Currently we manually add target_board_api_level, but it might be useful
    # to come up with something more generic
    #
    # TODO: there are some macros that look like this
    # define(`FIOCLEX', ifelse(target_arch, mips, 0x00006601, 0x00005451))
    # which do not seem to be valid because the condition value is unquoted,
    # while all other conditions have their values quoted
    # Find out what to do about them

    conditionals_values: Dict[str, Set[str]] = {}

    def add_conditionals(key: str, value: str):
        if key not in conditionals_values:
            conditionals_values[key] = set()
        conditionals_values[key].add(value)

    # Find variables and values checked against
    for m in ifelse_arg_variable_pattern.finditer(body):
        key = m.group(1)
        value = m.group(2)

        if '$' in key:
            assert name is not None, body

            if (name, key) in HANDLED_VARIABLE_MACRO_IFELSE:
                continue

            print(f'Macro {name} contains variable ifelse: {key}')
            continue

        add_conditionals(key, value)

    # TODO: implement this properly by allowing macros to have conditional
    # rules based on input params
    for m in is_flag_enabled_regex.finditer(body):
        add_conditionals(f'{TARGET_FLAG_PREFIX}{m.group(1)}', 'true')

    # Add another value that is unknown to take else branch of ifelse
    # into account
    for values in conditionals_values.values():
        values.add('__UNKNOWN__')

    return conditionals_values


def names_pattern(macro_names: List[str]):
    # Sort descending length for optimal regex
    macro_names.sort(key=len, reverse=True)

    # Escape names
    escaped_macro_names = [re.escape(mn) for mn in macro_names]

    # Join them together into a pattern
    no_arity_pattern_text = rf'\b({"|".join(escaped_macro_names)})\b'

    return re.compile(no_arity_pattern_text)


def macro_used_macros(body: str):
    for m in macro_call_pattern.finditer(body):
        name = m.group(1)
        if name in BUILTIN_CALLS:
            continue

        yield name


def define_variable(k: str, v: str):
    return f"define(`{k}', `{v}')\n"


def macro_arity(body: str):
    found_args = macro_arity_pattern.finditer(body)
    used_args = set(int(m.group(1)) for m in found_args)
    return max(used_args) if used_args else 0


@cache
def arity_dummy_args(arity: int):
    return ', '.join(f"`${i}'" for i in range(1, arity + 1))


def macro_dummy_call(name: str, arity: int):
    dummy_args = arity_dummy_args(arity)

    # Define a macro that expands to its expanded definition, quoted
    # Double quote the macro name to prevent its expansion
    return f"`define'(``{name}'', quote_start()\n{name}({dummy_args})\nquote_end())\n"


def used_variables_choices(
    used_variables: Set[str],
    variables_choices: Dict[str, Set[str]],
):
    return {k: variables_choices[k] for k in used_variables}


def quote_char(c: str):
    change = 'changequote([,])'
    unchange = "changequote(`,')"
    return f'{change}[{change}{c}{unchange}]{unchange}'


@dataclass
class ProcessedMacro:
    text: str
    name: Optional[str]
    body: str
    arity: int
    used_macros: Set[str]
    used_variables: Set[str]
    is_rule: bool
    is_unquoted_ifelse: bool
    is_any_macro_unquoted_ifelse: bool
    recursively_used_macros: List[str] = field(
        default_factory=lambda: list(),
    )
    recursively_used_variables: Set[str] = field(
        default_factory=lambda: set(),
    )
    recursively_used_macros_processed: bool = field(default=False)


def macro_recursive_used_macros(
    macro: ProcessedMacro,
    processed_macros: Dict[str, ProcessedMacro],
) -> Generator[str, None, None]:
    if macro.name is not None:
        yield macro.name

    for macro_name in macro.used_macros:
        yield from macro_recursive_used_macros(
            processed_macros[macro_name],
            processed_macros,
        )


def macro_names_used_variables(
    macro_names: Iterable[str],
    processed_macros: Dict[str, ProcessedMacro],
) -> Generator[str, None, None]:
    for macro_name in macro_names:
        macro = processed_macros[macro_name]
        yield from macro.used_variables


def expand_macro_bodies(
    macros: List[str],
    all_variables_choices: Dict[str, Set[str]],
):
    # Define macros used to change the quote format
    # This is used to add ` and ' around the expanded macro body
    # Macro expansion does not happen when the macro text is
    # quoted more than once
    # Use the standard way of defining macros so that the macro
    # definition functions can be re-used
    input_text = f"""
define(`quote_start', {quote_char('`')})
define(`quote_end', {quote_char("'")})
"""

    # Create patterns for variables
    # target_flag_ needs to be removed to create a dependency between the
    # rule using the flag and the flag itself, since is_flag_enabled() only
    # depends on target_flag_$1
    # TODO: fix
    target_flags: Set[str] = set()
    dependency_all_variables_choices: Dict[str, Set[str]] = {}
    for name, value in all_variables_choices.items():
        if name.startswith(TARGET_FLAG_PREFIX):
            name = name.removeprefix(TARGET_FLAG_PREFIX)
            target_flags.add(name)

        dependency_all_variables_choices[name] = value

    variable_names = list(dependency_all_variables_choices.keys())
    variables_pattern = names_pattern(variable_names)

    # Gather all macros and variables used by each macro
    found_macros: Set[str] = set()
    processed_macros: Dict[str, ProcessedMacro] = {}
    processed_rules: List[ProcessedMacro] = []
    no_arity_macro_names: List[str] = []
    for macro in macros:
        name, body = macro_name_body_raw(macro)
        used_macros = set(macro_used_macros(body))

        # Free-standing rules do not have a name but can use other macros
        # TODO: check if non-macro rules have conditional variables?
        used_variables: Set[str] = set()
        for match in variables_pattern.finditer(body):
            used_variables.add(match.group(1))

        arity = macro_arity(macro)
        is_unquoted_ifelse = macro_is_unquoted_ifelse(body)
        is_rule = name is None
        processed_macro = ProcessedMacro(
            macro,
            name,
            body,
            arity,
            used_macros,
            used_variables,
            is_rule,
            is_unquoted_ifelse,
            is_any_macro_unquoted_ifelse=is_unquoted_ifelse,
        )

        if name in found_macros:
            color_print(f'Duplicate macro with name {name}', color=Color.YELLOW)
            continue

        if name is None:
            processed_rules.append(processed_macro)
            continue

        processed_macros[name] = processed_macro
        found_macros.add(name)

        if not arity:
            no_arity_macro_names.append(name)

    # Find all used no-arity macros in all macros and rules
    if no_arity_macro_names:
        no_arity_pattern = names_pattern(no_arity_macro_names)

        for macro in chain(processed_macros.values(), processed_rules):
            for match in no_arity_pattern.finditer(macro.body):
                macro.used_macros.add(match.group(1))

    # Find macros that do not use any variables recursively
    # TODO: optimize
    simple_macros: List[ProcessedMacro] = []
    for macro in chain(processed_macros.values(), processed_rules):
        # Find all used macros recursively
        # TODO: cache
        used_macro_names = list(
            macro_recursive_used_macros(
                macro,
                processed_macros,
            )
        )

        # Find all used variables recursively
        used_variables = set(
            macro_names_used_variables(
                used_macro_names,
                processed_macros,
            )
        )

        # Remove own macro name from list
        if macro.name is not None:
            used_macro_names.remove(macro.name)

        # Add own used variables since rules do not have a name and cannot be
        # gathered by macro_recursive_used_macros()
        macro.recursively_used_variables.update(macro.used_variables)

        macro.recursively_used_macros.extend(used_macro_names)
        macro.recursively_used_variables.update(used_variables)

        if not macro.is_any_macro_unquoted_ifelse:
            macro.is_any_macro_unquoted_ifelse = any(
                processed_macros[m].is_unquoted_ifelse for m in used_macro_names
            )

        # Rules that expand macros cannot be simple
        is_complex_rule = macro.is_rule and macro.used_macros
        if not macro.is_any_macro_unquoted_ifelse and not is_complex_rule:
            simple_macros.append(macro)

    # Output macros that don't use unquoted ifelse() statements even recursively
    for macro in simple_macros:
        input_text += macro.text + '\n'

    # TODO: optimize
    for macro in chain(processed_macros.values(), processed_rules):
        # Filter the variable choices based on the used variables
        variables_choices = used_variables_choices(
            macro.recursively_used_variables,
            dependency_all_variables_choices,
        )

        dummy_call = ''
        # We do not need to produce defines() for rules, skip dummy calls
        if not macro.is_rule:
            assert macro.name is not None
            dummy_call = macro_dummy_call(macro.name, macro.arity)
            dummy_call += '\n'

        for combined_variables in combine_variable_choices(variables_choices):
            for k, v in combined_variables.items():
                # TODO: fix
                if k in target_flags:
                    k = f'{TARGET_FLAG_PREFIX}{k}'

                input_text += define_variable(k, v)

            # Output used macros that are not simple, which should only be
            # unquoted ifelse() macros
            for used_macro_name in macro.recursively_used_macros:
                used_macro = processed_macros[used_macro_name]
                if used_macro.is_any_macro_unquoted_ifelse:
                    input_text += used_macro.text + '\n'

            input_text += macro.text + '\n'
            input_text += dummy_call
            input_text += '\n\n'

    output_text = subprocess.check_output(
        ['m4'],
        input=input_text,
        text=True,
    )

    return output_text


def combine_variable_choices(
    variables_choices: Dict[str, Set[str]],
) -> Generator[Dict[str, str], None, None]:
    # List of (variable_name, value) tuples for each possible value
    # of each variable name
    expanded_choices = [
        [(k, v) for v in list(vals)] for k, vals in variables_choices.items()
    ]

    for values in itertools.product(*expanded_choices):
        yield dict(values)


def categorize_macros(expanded_macros_text: str):
    expanded_macros: List[Tuple[str, str]] = []
    class_sets: List[Tuple[str, str]] = []
    perms: List[Tuple[str, str]] = []
    ioctls: List[Tuple[str, str]] = []
    ioctl_defines: List[Tuple[str, str]] = []
    rules: List[str] = []

    empty_macros: Set[str] = set()
    for macro_text in split_rules(split_normalize_text(expanded_macros_text)):
        name, body = macro_name_body(macro_text)
        if not name:
            rules.append(body)
            continue

        assert body is not None
        if not body:
            if name in empty_macros:
                continue

            color_print(f'Empty macro {name}', color=Color.YELLOW)
            empty_macros.add(name)
            continue

        # Compiled ioctls only keep the bottom two bytes
        # Do the same here to get more matches
        if body.startswith('0x'):
            body = format_ioctl_str(body)

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

    return expanded_macros, class_sets, perms, ioctls, ioctl_defines, rules


# Extracted from system/sepolicy/build/soong/policy.go
SEPOLICY_FILES = [
    'global_macros',
    'neverallow_macros',
    'te_macros',
    'ioctl_defines',
    'ioctl_macros',
    'attributes',
]

SEPOLICY_FILES_PREFIXES = [
    'public',
    'private',
]


def resolve_macro_paths(
    macro_paths: List[str],
    system_sepolicy_path: Optional[Path] = None,
):
    macro_file_paths: List[str] = []
    access_vectors_path: Optional[Path] = None
    flagging_macros_path: Optional[Path] = None

    # These do not exist per-version
    if system_sepolicy_path is not None:
        flagging_macros_path = Path(
            system_sepolicy_path,
            'flagging/flagging_macros',
        )
        if flagging_macros_path.is_file():
            macro_file_paths.append(str(flagging_macros_path))

    for macro_path in macro_paths:
        mp = Path(macro_path)
        if mp.is_file():
            macro_file_paths.append(str(mp.resolve()))
            continue

        if not mp.is_dir():
            color_print(
                f'Macro path {macro_path} is not a file or directory',
                color=Color.RED,
            )
            continue

        for file_path in SEPOLICY_FILES:
            for prefix in SEPOLICY_FILES_PREFIXES:
                fp = Path(macro_path, prefix, file_path)

                if fp.is_file():
                    macro_file_paths.append(str(fp.resolve()))

        fp = Path(macro_path, 'private/access_vectors')
        if fp.is_file():
            assert access_vectors_path is None
            access_vectors_path = fp

    return macro_file_paths, access_vectors_path, flagging_macros_path


def read_macros(macro_file_paths: List[str]) -> List[str]:
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
    macros_text = list(split_rules(input_text_lines))

    return macros_text


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
        except ValueError as e:
            if name not in invalid_macro_names:
                color_print(f'Invalid macro {name}: {e}', color=Color.YELLOW)
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
        flattened_parts = list(flatten_parts(parts))
        unpacked_ioctls = list(unpack_ioctls(flattened_parts))
        try:
            parts_set = set(chain.from_iterable(unpacked_ioctls))
        except ValueError:
            color_print(
                f'Ioctl macro {name} contains invalid ioctls: {text}',
                color=Color.RED,
            )
            continue

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

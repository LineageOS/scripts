# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import subprocess
from enum import StrEnum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from sepolicy.macro import (
    TARGET_FLAG_PREFIX,
    combine_variable_choices,
    define_variable,
    names_pattern,
    used_variables_choices,
)
from sepolicy.rule import Rule
from sepolicy.rules import (
    ALLOWED_ROOT_SYSTEM_SEPOLICY_RULES_SUBDIRS,
    split_rules,
)
from sepolicy.source_rule import SourceRule
from utils.utils import Color, color_print, split_normalize_text


class ContextsType(StrEnum):
    PROPERTY_CONTEXTS_NAME = 'property_contexts'
    FILE_CONTEXTS_NAME = 'file_contexts'
    HWSERVICE_CONTEXTS_NAME = 'hwservice_contexts'
    VNDSERVICE_CONTEXTS_NAME = 'vndservice_contexts'
    SERVICE_CONTEXTS_NAME = 'service_contexts'
    SEAPP_CONTEXTS_NAME = 'seapp_contexts'
    GENFS_CONTEXTS_NAME = 'genfs_contexts'


def resolve_contexts_paths(
    contexts_paths: List[Path],
    partition_name: Optional[str],
    system_sepolicy_path: Optional[Path],
    verbose: bool,
):
    contexts_file_paths: Dict[ContextsType, List[Path]] = {}

    def add_contexts_file_path(fp: Path):
        if not fp.is_file():
            return

        for contexts_type in ContextsType:
            if (
                partition_name is not None
                and contexts_type != ContextsType.VNDSERVICE_CONTEXTS_NAME
            ):
                file_name = f'{partition_name}_{contexts_type.value}'
            else:
                file_name = contexts_type.value

            if fp.name != file_name:
                continue

            if contexts_type not in contexts_file_paths:
                contexts_file_paths[contexts_type] = []

            contexts_file_paths[contexts_type].append(fp)
            if verbose:
                print(f'Loading contexts: {fp}')

    for contexts_path in contexts_paths:
        if contexts_path.is_file():
            add_contexts_file_path(contexts_path)
            continue

        # --current uses the root directory, which contains a lot of .te
        # files from other versions of the API too
        if contexts_path == system_sepolicy_path:
            subdirs_to_scan = [
                Path(contexts_path, subdir_name)
                for subdir_name in ALLOWED_ROOT_SYSTEM_SEPOLICY_RULES_SUBDIRS
            ]
        else:
            subdirs_to_scan = [contexts_path]

        for file_subdir in subdirs_to_scan:
            if verbose:
                print(f'Loading contexts from directory: {file_subdir}')

            if not file_subdir.is_dir():
                color_print(
                    f'Contexts path {file_subdir} is not a file or directory',
                    color=Color.RED,
                )
                continue

            for file_path in file_subdir.rglob('*_contexts'):
                add_contexts_file_path(file_path)

    return contexts_file_paths


def split_contexts_text(contexts_file_paths: Dict[ContextsType, List[Path]]):
    contexts_texts: Dict[ContextsType, List[str]] = {}

    for contexts_type, file_paths in contexts_file_paths.items():
        contexts_texts[contexts_type] = []

        for file_path in file_paths:
            text = file_path.read_text()
            for rule in split_rules(
                split_normalize_text(text),
                # Only end a rule if level is 0 and line ended
                ending_char='\n',
                # We make the assumption that anyone writing macro calls in
                # contexts won't place stray characters anywhere...
                # This will blow up later if that's the case
                only_end_at_ending_char=True,
            ):
                contexts_texts[contexts_type].append(rule)

    return contexts_texts


def expand_context_texts(
    context_texts: List[str],
    all_variables_choices: Dict[str, Set[str]],
    flagging_macros_path: Optional[Path],
    version: str,
):
    input_text = ''

    if flagging_macros_path is not None:
        input_text = flagging_macros_path.read_text()

    # TODO: deduplicate this logic from expand_macro_bodies()
    target_flags: Set[str] = set()
    dependency_all_variables_choices: Dict[str, Set[str]] = {}
    for name, value in all_variables_choices.items():
        if name.startswith(TARGET_FLAG_PREFIX):
            name = name.removeprefix(TARGET_FLAG_PREFIX)
            target_flags.add(name)

        dependency_all_variables_choices[name] = value

    variable_names = list(dependency_all_variables_choices.keys())
    variables_pattern = names_pattern(variable_names)

    for context_text in context_texts:
        used_variables: Set[str] = set()
        for match in variables_pattern.finditer(context_text):
            used_variables.add(match.group(1))

        if used_variables:
            assert flagging_macros_path is not None

        variables_choices = used_variables_choices(
            used_variables,
            dependency_all_variables_choices,
        )

        for combined_variables in combine_variable_choices(variables_choices):
            for k, v in combined_variables.items():
                # TODO: fix
                if k in target_flags:
                    k = f'{TARGET_FLAG_PREFIX}{k}'

                input_text += define_variable(k, v)

            input_text += context_text
            input_text += '\n'

    # TODO: unify this with macro processing
    text = subprocess.check_output(
        ['m4', '-D', f'target_board_api_level={version}'],
        input=input_text,
        text=True,
    )

    return split_normalize_text(text)


def expand_contexts_texts(
    contexts_texts: Dict[ContextsType, List[str]],
    all_variables_choices: Dict[str, Set[str]],
    flagging_macros_path: Optional[Path],
    version: str,
):
    contexts: Dict[ContextsType, List[str]] = {}

    for contexts_type, context_texts in contexts_texts.items():
        contexts[contexts_type] = expand_context_texts(
            context_texts,
            all_variables_choices,
            flagging_macros_path,
            version,
        )

    return contexts


def parse_contexts_texts(contexts_texts: Dict[ContextsType, List[str]]):
    contexts: Dict[ContextsType, List[Tuple[str, ...]]] = {}
    genfs_rules: List[Rule] = []

    for contexts_type, context_texts in contexts_texts.items():
        contexts[contexts_type] = []

        if contexts_type == ContextsType.GENFS_CONTEXTS_NAME:
            for context_text in context_texts:
                context_text = context_text.strip()

                genfs_rule = SourceRule.genfscon_from_line(context_text)
                genfs_rules.append(genfs_rule)

            continue

        for context_text in context_texts:
            context_text = context_text.strip()
            context_parts = context_text.split(' ')
            contexts[contexts_type].append(tuple(context_parts))

    return contexts, genfs_rules


def remove_source_contexts(
    contexts: Dict[ContextsType, List[Tuple[str, ...]]],
    source_contexts: Dict[ContextsType, List[Tuple[str, ...]]],
):
    new_contexts: Dict[ContextsType, List[Tuple[str, ...]]] = {}

    for contexts_type, contexts_rules in contexts.items():
        if contexts_type not in source_contexts:
            continue

        source_contexts_rules_set = set(source_contexts[contexts_type])
        new_contexts_rules: List[Tuple[str, ...]] = []
        removed_rules = 0
        for rule in contexts_rules:
            if rule in source_contexts_rules_set:
                removed_rules += 1
                continue

            new_contexts_rules.append(rule)

        color_print(
            f'Removed {removed_rules} {contexts_type} source rules',
            color=Color.GREEN,
        )

        new_contexts[contexts_type] = new_contexts_rules

    return new_contexts


def remove_source_genfs_rules(
    genfs_rules: List[Rule],
    source_genfs_rules: List[Rule],
):
    source_genfs_rules_set = set(source_genfs_rules)
    clean_genfs_rules: List[Rule] = []
    removed_rules = 0

    for rule in genfs_rules:
        if rule in source_genfs_rules_set:
            removed_rules += 1
            continue

        clean_genfs_rules.append(rule)

    color_print(
        f'Removed {removed_rules} {ContextsType.GENFS_CONTEXTS_NAME.value} source rules',
        color=Color.GREEN,
    )

    return clean_genfs_rules


def output_contexts(
    contexts: Dict[ContextsType, List[Tuple[str, ...]]],
    output_dir: Path,
):
    for contexts_type, contexts_rules in contexts.items():
        if not contexts_rules:
            continue

        output_contexts_path = output_dir / contexts_type
        with open(output_contexts_path, 'w') as o:
            for rule_parts in contexts_rules:
                rule_str = ' '.join(rule_parts)
                o.write(rule_str)
                o.write('\n')


def output_genfs_contexts(genfs_rules: List[Rule], output_dir: Path):
    if not genfs_rules:
        return

    output_path = output_dir / ContextsType.GENFS_CONTEXTS_NAME
    with open(output_path, 'w') as o:
        for rule in genfs_rules:
            o.write(str(rule))
            o.write('\n')


DOMAIN_PREFIX = 'domain='


def find_contexts_used_types(
    contexts: Dict[ContextsType, List[Tuple[str, ...]]],
    used_types: Set[str],
):
    for contexts_type, contexts_rules in contexts.items():
        assert contexts_type != ContextsType.GENFS_CONTEXTS_NAME

        for rule in contexts_rules:
            match contexts_type:
                case (
                    ContextsType.PROPERTY_CONTEXTS_NAME
                    | ContextsType.FILE_CONTEXTS_NAME
                    | ContextsType.HWSERVICE_CONTEXTS_NAME
                    | ContextsType.VNDSERVICE_CONTEXTS_NAME
                    | ContextsType.SERVICE_CONTEXTS_NAME
                ):
                    used_types.add(rule[1])
                case ContextsType.SEAPP_CONTEXTS_NAME:
                    for part in rule:
                        if part.startswith(DOMAIN_PREFIX):
                            part = part[len(DOMAIN_PREFIX) :]
                            used_types.add(part)

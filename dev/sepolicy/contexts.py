# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from sepolicy.rule import Rule, trim_contexts_label
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
    BUG_MAP_NAME = 'bug_map'


CONTEXTS_ALTERNATIVE_FILE_NAMES = {
    ContextsType.BUG_MAP_NAME: ['selinux_denial_metadata'],
}

CONTEXTS_NO_PARTITION_PREFIX = {
    ContextsType.BUG_MAP_NAME: True,
}


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
            file_names: List[str] = [
                contexts_type.value,
                *CONTEXTS_ALTERNATIVE_FILE_NAMES.get(contexts_type, []),
            ]

            for file_name in file_names:
                if (
                    partition_name is not None
                    and not CONTEXTS_NO_PARTITION_PREFIX.get(
                        contexts_type, False
                    )
                    and contexts_type != ContextsType.VNDSERVICE_CONTEXTS_NAME
                ):
                    file_name = f'{partition_name}_{file_name}'

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

            for file_path in file_subdir.rglob('*'):
                add_contexts_file_path(file_path)

    return contexts_file_paths


def split_normalize_contexts_text(text: str):
    input_text_lines = split_normalize_text(text)

    return list(
        split_rules(
            input_text_lines,
            # Only end a rule if level is 0 and line ended
            ending_char='\n',
            # We make the assumption that anyone writing macro calls in
            # contexts won't place stray characters anywhere...
            # This will blow up later if that's the case
            only_end_at_ending_char=True,
        )
    )


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

        unique_rules_set: Set[Tuple[str, ...]] = set()
        joined_contexts: List[str] = []
        for rule in contexts_rules:
            if rule in unique_rules_set:
                continue

            unique_rules_set.add(rule)
            joined_rule = f'{" ".join(rule)}\n'
            joined_contexts.append(joined_rule)

        joined_contexts.sort()
        output_text = ''.join(joined_contexts)

        output_contexts_path = output_dir / contexts_type
        output_contexts_path.write_text(output_text)


def output_genfs_contexts(genfs_rules: List[Rule], output_dir: Path):
    if not genfs_rules:
        return

    output_path = output_dir / ContextsType.GENFS_CONTEXTS_NAME
    with open(output_path, 'w') as o:
        for rule in genfs_rules:
            o.write(str(rule))
            o.write('\n')


DOMAIN_PREFIX = 'domain='
TYPE_PREFIX = 'type='


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
                    t = trim_contexts_label(rule[1])
                    used_types.add(t)
                case ContextsType.BUG_MAP_NAME:
                    used_types.add(rule[0])
                    used_types.add(rule[1])
                case ContextsType.SEAPP_CONTEXTS_NAME:
                    for part in rule:
                        if part.startswith(DOMAIN_PREFIX):
                            part = part[len(DOMAIN_PREFIX) :]
                            used_types.add(part)
                        elif part.startswith(TYPE_PREFIX):
                            part = part[len(TYPE_PREFIX) :]
                            used_types.add(part)

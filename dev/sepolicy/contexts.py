# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Set, Tuple

from sepolicy.policy import ContextsType
from sepolicy.rule import trim_contexts_label
from sepolicy.rule_container import RuleContainer
from sepolicy.rules import split_rules
from sepolicy.source_rule import SourceRule
from utils.utils import split_normalize_text


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


def parse_genfs_contexts(texts: List[str]):
    genfs_rules = RuleContainer()

    for text in texts:
        text = text.strip()

        genfs_rule = SourceRule.genfscon_from_line(text)
        genfs_rules.add(genfs_rule)

    return genfs_rules


def parse_contexts_texts(texts: List[str]):
    contexts: List[Tuple[str, ...]] = []

    for text in texts:
        text = text.strip()
        context_parts = text.split(' ')
        contexts.append(tuple(context_parts))

    return contexts


def remove_source_contexts(
    contexts: Dict[ContextsType, List[Tuple[str, ...]]],
    source_contexts: Dict[ContextsType, List[Tuple[str, ...]]],
):
    new_contexts: Dict[ContextsType, List[Tuple[str, ...]]] = {}
    removed_rules = 0

    for contexts_type, contexts_rules in contexts.items():
        if contexts_type not in source_contexts:
            new_contexts[contexts_type] = contexts_rules
            continue

        source_contexts_rules_set = set(source_contexts[contexts_type])
        new_contexts_rules: List[Tuple[str, ...]] = []
        for rule in contexts_rules:
            if rule in source_contexts_rules_set:
                removed_rules += 1
                continue

            new_contexts_rules.append(rule)

        new_contexts[contexts_type] = new_contexts_rules

    return new_contexts, removed_rules


def remove_source_genfs_rules(
    genfs_rules: RuleContainer,
    source_genfs_rules: RuleContainer,
):
    clean_genfs_rules = RuleContainer()
    removed_rules = 0

    for rule in genfs_rules:
        if rule in source_genfs_rules:
            removed_rules += 1
            continue

        clean_genfs_rules.add(rule)

    return clean_genfs_rules, removed_rules


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


def output_genfs_contexts(genfs_rules: RuleContainer, output_dir: Path):
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

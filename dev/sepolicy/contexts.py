# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Set, Tuple

from sepolicy.policy import ContextsType
from sepolicy.rule_container import RuleContainer
from sepolicy.source_rule import SourceRuleParser


def parse_genfs_contexts(texts: List[str]):
    genfs_rules = RuleContainer()

    for text in texts:
        text = text.strip()

        genfs_rule = SourceRuleParser.genfscon_from_line(text)
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

    lines = sorted(f'{rule}\n' for rule in genfs_rules)

    output_path = output_dir / ContextsType.GENFS_CONTEXTS_NAME
    output_path.write_text(''.join(lines))

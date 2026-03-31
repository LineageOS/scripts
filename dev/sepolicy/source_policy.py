# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set, Tuple

from sepolicy.cil_rule import CilRule
from sepolicy.classmap import Classmap
from sepolicy.contexts import (
    ContextsType,
    parse_contexts_texts,
    resolve_contexts_paths,
    split_normalize_contexts_text,
)
from sepolicy.expand import expand_macro_calls_and_variables
from sepolicy.macro import (
    categorize_macros,
    macro_required_name_body_raw,
    parse_ioctl_defines,
    parse_ioctls,
    parse_macros,
    parse_perms,
    resolve_macro_paths,
    rule_body,
)
from sepolicy.rule import Rule
from sepolicy.rules import (
    parse_rules,
    resolve_rule_paths,
    split_normalize_rules_text,
)
from utils.utils import read_texts


@dataclass
class SourceMacros:
    perms: List[Tuple[str, Set[str]]]
    class_sets: List[Tuple[str, Set[str]]]
    ioctls: List[Tuple[str, Set[str]]]
    nlmsgs: List[Tuple[str, Set[str]]]
    ioctl_defines: Dict[str, str]
    nlmsg_defines: Dict[str, str]
    macros_name_rules: List[Tuple[str, List[Rule]]]
    classmap: Classmap


@dataclass
class SourcePolicy:
    rules: List[Rule]
    genfs_rules: List[Rule]
    contexts: Dict[ContextsType, List[Tuple[str, ...]]]


def parse_source(
    macros_paths: List[Path],
    extra_macros_paths: List[Path],
    rules_paths: List[Path],
    extra_rules_paths: List[Path],
    system_sepolicy_path: Path,
    verbose: bool,
    version: str,
    variables: Dict[str, str],
):
    (
        macro_file_paths,
        ioctl_defines_file_paths,
        ioctl_macros_file_paths,
        nlmsg_defines_file_paths,
        nlmsg_macros_file_paths,
        technical_debt_path,
        access_vectors_path,
        flagging_macros_path,
    ) = resolve_macro_paths(
        macros_paths + extra_macros_paths,
        system_sepolicy_path,
        verbose,
    )

    rule_file_paths = resolve_rule_paths(
        rules_paths + extra_rules_paths,
        system_sepolicy_path,
        verbose,
    )

    contexts_file_paths = resolve_contexts_paths(
        rules_paths + extra_rules_paths,
        None,
        system_sepolicy_path,
        verbose,
    )

    macros_text = read_texts(macro_file_paths)
    rules_text = read_texts(rule_file_paths)
    ioctl_defines_text = read_texts(ioctl_defines_file_paths)
    nlmsg_defines_text = read_texts(nlmsg_defines_file_paths)
    ioctl_macros_text = read_texts(ioctl_macros_file_paths)
    nlmsg_macros_text = read_texts(nlmsg_macros_file_paths)
    flagging_macros_text = read_texts([flagging_macros_path])
    contexts_text = {
        name: read_texts(context_file_paths)
        for name, context_file_paths in contexts_file_paths.items()
    }

    base_environment_texts = [
        flagging_macros_text,
    ]

    macros_environment_texts = [
        flagging_macros_text,
        ioctl_defines_text,
        ioctl_macros_text,
        nlmsg_defines_text,
        nlmsg_macros_text,
    ]

    ioctl_defines = expand_macro_calls_and_variables(
        text=ioctl_defines_text,
        environment_texts=base_environment_texts,
        variables=variables,
        split_fn=split_normalize_rules_text,
        map_fn=macro_required_name_body_raw,
        text_name='ioctl_defines',
        verbose=verbose,
    )

    nlmsg_defines = expand_macro_calls_and_variables(
        text=nlmsg_defines_text,
        environment_texts=base_environment_texts,
        variables=variables,
        split_fn=split_normalize_rules_text,
        map_fn=macro_required_name_body_raw,
        text_name='nlmsg_defines',
        verbose=verbose,
    )

    ioctl_macros = expand_macro_calls_and_variables(
        text=ioctl_macros_text,
        environment_texts=[
            *base_environment_texts,
            ioctl_defines_text,
        ],
        variables=variables,
        split_fn=split_normalize_rules_text,
        map_fn=macro_required_name_body_raw,
        text_name='ioctl_macros',
        verbose=verbose,
    )

    nlmsg_macros = expand_macro_calls_and_variables(
        text=nlmsg_macros_text,
        environment_texts=[
            *base_environment_texts,
            nlmsg_defines_text,
        ],
        variables=variables,
        split_fn=split_normalize_rules_text,
        map_fn=macro_required_name_body_raw,
        text_name='nlmsg_macros',
        verbose=verbose,
    )

    expanded_macros = expand_macro_calls_and_variables(
        text=macros_text,
        environment_texts=macros_environment_texts,
        variables=variables,
        split_fn=split_normalize_rules_text,
        map_fn=macro_required_name_body_raw,
        text_name='expanded_macros',
        verbose=verbose,
    )

    expanded_rules = expand_macro_calls_and_variables(
        text=rules_text,
        environment_texts=[
            *macros_environment_texts,
            macros_text,
        ],
        variables=variables,
        split_fn=split_normalize_rules_text,
        map_fn=rule_body,
        text_name='expanded_rules',
        verbose=verbose,
    )

    expanded_contexts = {
        name: expand_macro_calls_and_variables(
            text=context_text,
            environment_texts=base_environment_texts,
            variables=variables,
            split_fn=split_normalize_contexts_text,
            map_fn=lambda s: s,
            text_name=name,
            verbose=verbose,
        )
        for name, context_text in contexts_text.items()
    }

    source_contexts, source_genfs_rules = parse_contexts_texts(
        expanded_contexts,
    )

    (
        macros,
        class_sets,
        perms,
    ) = categorize_macros(expanded_macros)

    source_perms = parse_perms(perms)
    source_class_sets = parse_perms(class_sets)
    source_ioctls = parse_ioctls(ioctl_macros, is_nlmsg=False)
    source_nlmsgs = parse_ioctls(nlmsg_macros, is_nlmsg=True)
    source_ioctl_defines = parse_ioctl_defines(
        ioctl_defines,
        verbose,
        is_nlmsg=False,
    )
    source_nlmsg_defines = parse_ioctl_defines(
        nlmsg_defines,
        verbose,
        is_nlmsg=True,
    )

    classmap = Classmap(flagging_macros_path, version, access_vectors_path)
    macros_name_rules = parse_macros(classmap, macros)
    source_rules = parse_rules(classmap, expanded_rules)

    def add_rule(rule: Rule):
        source_rules.append(rule)

    if technical_debt_path is not None:
        for line in technical_debt_path.read_text().splitlines():
            CilRule.from_line(
                line,
                conditional_types_map={},
                missing_generated_types=set(),
                add_rule=add_rule,
                add_genfs_rule=None,
                version=version,
            )

    # This rule is automatically added by
    # external/selinux/libsepol/src/module_to_cil.c
    source_rules.append(Rule('attribute', ('cil_gen_require',), ()))

    return (
        SourcePolicy(
            rules=source_rules,
            contexts=source_contexts,
            genfs_rules=source_genfs_rules,
        ),
        SourceMacros(
            perms=source_perms,
            class_sets=source_class_sets,
            ioctls=source_ioctls,
            nlmsgs=source_nlmsgs,
            ioctl_defines=source_ioctl_defines,
            nlmsg_defines=source_nlmsg_defines,
            macros_name_rules=macros_name_rules,
            classmap=classmap,
        ),
    )

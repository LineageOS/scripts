# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass
from itertools import chain
from pathlib import Path
from typing import Dict, List, Set, Tuple

from sepolicy.cil_policy import decompile_one_cil
from sepolicy.classmap import Classmap
from sepolicy.contexts import (
    ContextsType,
    expand_contexts_texts,
    parse_contexts_texts,
    resolve_contexts_paths,
    split_contexts_text,
)
from sepolicy.macro import (
    categorize_macros,
    expand_macro_bodies,
    macro_name_body_raw,
    macro_used_variables,
    parse_ioctl_defines,
    parse_ioctls,
    parse_macros,
    parse_perms,
    resolve_macro_paths,
    split_ioctl_defines,
    split_macros_text,
)
from sepolicy.rule import Rule
from sepolicy.rules import parse_rules, resolve_rule_paths


@dataclass
class SourcePolicy:
    rules: List[Rule]
    genfs_rules: List[Rule]
    perms: List[Tuple[str, Set[str]]]
    class_sets: List[Tuple[str, Set[str]]]
    ioctls: List[Tuple[str, Set[str]]]
    nlmsgs: List[Tuple[str, Set[str]]]
    ioctl_defines: Dict[str, str]
    nlmsg_defines: Dict[str, str]
    macros_name_rules: List[Tuple[str, List[Rule]]]
    contexts: Dict[ContextsType, List[Tuple[str, ...]]]
    classmap: Classmap


def get_variable_choices(
    args_variables: List[str],
    macros_texts: List[List[str]],
    contexts_texts: Dict[ContextsType, List[str]],
    version: str,
):
    all_variables_choices: Dict[str, Set[str]] = {}

    # Find conditional variables used in the input text
    # Conditional variables can be specified, but we need to know if the
    # macro arguments are used in them
    for macros_text in macros_texts:
        for macro_text in macros_text:
            name, body = macro_name_body_raw(macro_text)
            conditional_variables = macro_used_variables(name, body)
            all_variables_choices.update(conditional_variables)

    for context_texts in contexts_texts.values():
        for context_text in context_texts:
            conditional_variables = macro_used_variables(None, context_text)
            all_variables_choices.update(conditional_variables)

    # Variables extracted from system/sepolicy/build/soong/policy.go
    all_variables_choices['mls_num_sens'] = set(['1'])
    all_variables_choices['mls_num_cats'] = set(['1024'])

    all_variables_choices['target_board_api_level'] = set([version])

    for kv in args_variables:
        k, v = kv.split('=')
        if k not in all_variables_choices:
            all_variables_choices[k] = set()

        all_variables_choices[k].add(v)

    print('Using variables:')
    for k, vs in all_variables_choices.items():
        print(f'{k}={", ".join(vs)}')

    return all_variables_choices


def parse_source(
    macros_paths: List[Path],
    extra_macros_paths: List[Path],
    rules_paths: List[Path],
    extra_rules_paths: List[Path],
    system_sepolicy_path: Path,
    args_variables: List[str],
    verbose: bool,
    version: str,
):
    (
        macro_file_paths,
        ioctl_defines_file_paths,
        nlmsg_defines_file_paths,
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

    macro_file_paths += rule_file_paths
    macros_texts = split_macros_text(macro_file_paths)
    ioctl_defines_texts = split_macros_text(ioctl_defines_file_paths)
    nlmsg_defines_texts = split_macros_text(nlmsg_defines_file_paths)

    source_contexts_file_paths = resolve_contexts_paths(
        rules_paths + extra_rules_paths,
        None,
        system_sepolicy_path,
        verbose,
    )
    source_contexts_texts = split_contexts_text(
        source_contexts_file_paths,
    )

    all_variables_choices = get_variable_choices(
        args_variables,
        [macros_texts, ioctl_defines_texts, nlmsg_defines_texts],
        source_contexts_texts,
        version,
    )

    expanded_ioctl_defines_text = expand_macro_bodies(
        ioctl_defines_texts,
        all_variables_choices,
        macros_handled_elsewhere=set(),
    )

    expanded_nlmsg_defines_text = expand_macro_bodies(
        nlmsg_defines_texts,
        all_variables_choices,
        macros_handled_elsewhere=set(),
    )

    ioctl_defines = split_ioctl_defines(expanded_ioctl_defines_text)
    nlmsg_defines = split_ioctl_defines(expanded_nlmsg_defines_text)

    # Prevent expand_macro_bodies() from expanding and assigning ioctls and
    # nlmsgs again, while also providing them for expansion
    ioctl_nlmsg_defines_names = set(
        name
        for name, _ in chain(
            ioctl_defines,
            nlmsg_defines,
        )
    )

    expanded_macros_text = expand_macro_bodies(
        macros_texts,
        all_variables_choices,
        macros_handled_elsewhere=ioctl_nlmsg_defines_names,
    )

    expanded_source_contexts_texts = expand_contexts_texts(
        source_contexts_texts,
        all_variables_choices,
        flagging_macros_path,
        version,
    )

    source_contexts, source_genfs_rules = parse_contexts_texts(
        expanded_source_contexts_texts,
    )

    (
        expanded_macros,
        class_sets,
        perms,
        ioctls,
        nlmsgs,
        source_rule_texts,
    ) = categorize_macros(expanded_macros_text)

    source_perms = parse_perms(perms)
    source_class_sets = parse_perms(class_sets)
    source_ioctls = parse_ioctls(ioctls, is_nlmsg=False)
    source_nlmsgs = parse_ioctls(nlmsgs, is_nlmsg=True)
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
    macros_name_rules = parse_macros(classmap, expanded_macros)
    source_rules = parse_rules(classmap, source_rule_texts)

    if technical_debt_path is not None:
        source_technical_debt_rules, _ = decompile_one_cil(
            technical_debt_path,
            {},
            set(),
            version,
            'source technical debt policy',
        )
        source_rules += source_technical_debt_rules

    # This rule is automatically added by
    # external/selinux/libsepol/src/module_to_cil.c
    source_rules.append(Rule('attribute', ('cil_gen_require',), ()))

    return SourcePolicy(
        rules=source_rules,
        contexts=source_contexts,
        genfs_rules=source_genfs_rules,
        perms=source_perms,
        class_sets=source_class_sets,
        ioctls=source_ioctls,
        nlmsgs=source_nlmsgs,
        ioctl_defines=source_ioctl_defines,
        nlmsg_defines=source_nlmsg_defines,
        macros_name_rules=macros_name_rules,
        classmap=classmap,
    )

# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import DefaultDict, Dict, List, Set, Tuple

from sepolicy.classmap import Classmap
from sepolicy.contexts import parse_contexts_texts, parse_genfs_contexts
from sepolicy.expand import expand_macro_calls, expand_macro_calls_and_split
from sepolicy.macro import (
    categorize_macros,
    macro_name_body,
    parse_ioctl_defines,
    parse_ioctls,
    parse_macros,
    parse_perms,
    rule_body,
)
from sepolicy.policy import (
    ContextsType,
    Policy,
    PolicyMetadata,
    PolicySourceOrigin,
    PolicyType,
    get_policy_type_by_name,
)
from sepolicy.rule_container import RuleContainer
from sepolicy.rules import split_normalize_rules_text
from sepolicy.source_macros import SourceMacros
from sepolicy.source_rule import SourceRuleParser
from sepolicy.source_text import PolicyFileType, SourceText
from utils.frozendict import FrozenDict
from utils.utils import android_root, read_texts, split_normalize_text

system_sepolicy_path = Path(android_root, 'system/sepolicy')


def get_source_policy_path(version: str, current: bool):
    if current:
        return system_sepolicy_path

    return Path(system_sepolicy_path, f'prebuilts/api/{version}')


def read_source_contexts_text(rules_paths: List[Tuple[Path, str]]):
    contexts_paths: DefaultDict[ContextsType, List[Path]] = defaultdict(list)

    for file_path, policy_name in rules_paths:
        policy_type = get_policy_type_by_name(policy_name)
        assert isinstance(policy_type.origin, PolicySourceOrigin)

        contexts_name_map = policy_type.origin.contexts_name_map
        if contexts_name_map is not None:
            for context_type, context_name in contexts_name_map.items():
                context_path = Path(file_path, context_name)
                if not context_path.is_file():
                    continue

                contexts_paths[context_type].append(context_path)

    contexts = {
        context_type: read_texts(context_paths)
        for context_type, context_paths in contexts_paths.items()
    }

    return contexts


def parse_source_rules(
    source_text: SourceText,
    variables: FrozenDict[str, str],
    classmap: Classmap,
    verbose: bool,
):
    expanded_rules = expand_macro_calls_and_split(
        texts=source_text.get_texts({PolicyFileType.TE}),
        environment_texts=source_text.get_texts(
            {
                PolicyFileType.FLAGGING_MACROS,
                PolicyFileType.IOCTL_DEFINES,
                PolicyFileType.NLMSG_DEFINES,
                PolicyFileType.IOCTL_MACROS,
                PolicyFileType.NLMSG_MACROS,
                PolicyFileType.GLOBAL_MACROS,
                PolicyFileType.NEVERALLOW_MACROS,
                PolicyFileType.TE_MACROS,
                PolicyFileType.ATTRIBUTES,
            }
        ),
        variables=variables,
        split_fn=split_normalize_rules_text,
        map_fn=rule_body,
        preserve_macros=False,
        text_name='expanded_rules',
        verbose=verbose,
    )

    rules = RuleContainer()

    parser = SourceRuleParser(
        rules.add,
        classmap,
    )
    for source_line in expanded_rules:
        parser.parse_line(source_line)

    return rules


def parse_source_contexts(
    contexts_text: Dict[ContextsType, str],
    source_macros_text: SourceText,
    variables: FrozenDict[str, str],
    verbose: bool,
):
    expanded_contexts = {
        context_type: expand_macro_calls_and_split(
            texts=[context_text],
            environment_texts=source_macros_text.get_texts(
                {PolicyFileType.FLAGGING_MACROS}
            ),
            variables=variables,
            split_fn=split_normalize_text,
            map_fn=lambda s: s,
            preserve_macros=False,
            text_name=context_type,
            verbose=verbose,
        )
        for context_type, context_text in contexts_text.items()
    }

    genfs_rules = RuleContainer()
    if ContextsType.GENFS_CONTEXTS_NAME in contexts_text:
        genfs_rules = parse_genfs_contexts(
            expanded_contexts[ContextsType.GENFS_CONTEXTS_NAME],
        )
        del expanded_contexts[ContextsType.GENFS_CONTEXTS_NAME]

    contexts = {
        context_type: parse_contexts_texts(context_texts)
        for context_type, context_texts in expanded_contexts.items()
    }

    return contexts, genfs_rules


def group_perms_by_class(perms: List[Tuple[str, Set[str]]], classmap: Classmap):
    # Sort longest perms first help the matching algorithm
    perms.sort(key=lambda np: len(np[1]), reverse=True)

    file_classes = list(classmap.class_types('file'))
    dir_classes = list(classmap.class_types('dir'))
    socket_classes = list(classmap.class_types('socket'))

    file_perms: List[Tuple[str, Set[str]]] = []
    dir_perms: List[Tuple[str, Set[str]]] = []
    socket_perms: List[Tuple[str, Set[str]]] = []

    for perm in perms:
        perm_name = perm[0]

        if '_file_' in perm_name:
            file_perms.append(perm)
        elif '_dir_' in perm_name:
            dir_perms.append(perm)
        elif '_socket_' in perm_name:
            socket_perms.append(perm)
        elif '_ipc_' in perm_name:
            # _ipc_ perms are unused, don't bother
            continue
        else:
            assert False, perm

    class_perms: DefaultDict[
        str,
        List[Tuple[str, Set[str]]],
    ] = defaultdict(list)

    for class_name in file_classes:
        class_perms[class_name] = file_perms

    for class_name in dir_classes:
        class_perms[class_name] = dir_perms

    for class_name in socket_classes:
        class_perms[class_name] = socket_perms

    return class_perms


def parse_source_macros(
    source_text: SourceText,
    variables: FrozenDict[str, str],
    classmap: Classmap,
    verbose: bool,
):
    ioctl_defines = expand_macro_calls_and_split(
        texts=source_text.get_texts({PolicyFileType.IOCTL_DEFINES}),
        environment_texts=source_text.get_texts(
            {
                PolicyFileType.FLAGGING_MACROS,
            }
        ),
        variables=variables,
        split_fn=split_normalize_rules_text,
        map_fn=macro_name_body,
        preserve_macros=True,
        text_name='ioctl_defines',
        verbose=verbose,
    )

    nlmsg_defines = expand_macro_calls_and_split(
        texts=source_text.get_texts({PolicyFileType.NLMSG_DEFINES}),
        environment_texts=source_text.get_texts(
            {
                PolicyFileType.FLAGGING_MACROS,
            }
        ),
        variables=variables,
        split_fn=split_normalize_rules_text,
        map_fn=macro_name_body,
        preserve_macros=True,
        text_name='nlmsg_defines',
        verbose=verbose,
    )

    ioctl_macros = expand_macro_calls_and_split(
        texts=source_text.get_texts({PolicyFileType.IOCTL_MACROS}),
        environment_texts=source_text.get_texts(
            {
                PolicyFileType.FLAGGING_MACROS,
                PolicyFileType.IOCTL_DEFINES,
            }
        ),
        variables=variables,
        split_fn=split_normalize_rules_text,
        map_fn=macro_name_body,
        preserve_macros=True,
        text_name='ioctl_macros',
        verbose=verbose,
    )

    nlmsg_macros = expand_macro_calls_and_split(
        texts=source_text.get_texts({PolicyFileType.NLMSG_MACROS}),
        environment_texts=source_text.get_texts(
            {
                PolicyFileType.FLAGGING_MACROS,
                PolicyFileType.NLMSG_DEFINES,
            }
        ),
        variables=variables,
        split_fn=split_normalize_rules_text,
        map_fn=macro_name_body,
        preserve_macros=True,
        text_name='nlmsg_macros',
        verbose=verbose,
    )

    expanded_macros = expand_macro_calls_and_split(
        texts=source_text.get_texts(
            {
                PolicyFileType.GLOBAL_MACROS,
                PolicyFileType.NEVERALLOW_MACROS,
                PolicyFileType.TE_MACROS,
                PolicyFileType.ATTRIBUTES,
            }
        ),
        environment_texts=source_text.get_texts(
            {
                PolicyFileType.FLAGGING_MACROS,
                PolicyFileType.IOCTL_DEFINES,
                PolicyFileType.NLMSG_DEFINES,
                PolicyFileType.IOCTL_MACROS,
                PolicyFileType.NLMSG_MACROS,
            }
        ),
        variables=variables,
        split_fn=split_normalize_rules_text,
        map_fn=macro_name_body,
        preserve_macros=True,
        text_name='expanded_macros',
        verbose=verbose,
    )

    (
        macros,
        class_sets,
        perms,
    ) = categorize_macros(expanded_macros)

    source_perms = parse_perms(perms)
    class_perms = group_perms_by_class(source_perms, classmap)

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

    macros_name_rules = parse_macros(
        classmap,
        macros,
    )

    return SourceMacros(
        class_perms=class_perms,
        class_sets=source_class_sets,
        ioctls=source_ioctls,
        nlmsgs=source_nlmsgs,
        ioctl_defines=source_ioctl_defines,
        nlmsg_defines=source_nlmsg_defines,
        macros_name_rules=macros_name_rules,
    )


def parse_source_classmap(
    flagging_macros_text: str,
    access_vectors_text: str,
    metadata: PolicyMetadata,
    verbose: bool,
):
    classmap_text = expand_macro_calls(
        [access_vectors_text],
        [flagging_macros_text],
        metadata.variables,
        preserve_macros=True,
        text_name='access_vectors',
        verbose=verbose,
    )

    return Classmap.from_text(classmap_text)


def parse_metadata_source_policies(
    rules_dir_paths: List[Tuple[Path, str]],
    policy_type: PolicyType,
    metadata: PolicyMetadata,
    source_text: SourceText,
    classmap: Classmap,
    verbose: bool,
):
    assert isinstance(policy_type.origin, PolicySourceOrigin)

    source_text.load_texts(
        tuple(v[0] for v in rules_dir_paths),
        # Only load rules
        allowed_types={PolicyFileType.TE},
    )

    contexts_text = read_source_contexts_text(rules_dir_paths)

    rules = parse_source_rules(
        source_text,
        metadata.variables,
        classmap,
        verbose=verbose,
    )

    contexts, genfs_rules = parse_source_contexts(
        contexts_text,
        source_text,
        metadata.variables,
        verbose=verbose,
    )

    return Policy(
        policy_type,
        rules,
        genfs_rules=genfs_rules,
        contexts=contexts,
        metadata=metadata,
        source_text=source_text,
    )

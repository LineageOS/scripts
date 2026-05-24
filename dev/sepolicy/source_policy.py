# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import (
    DefaultDict,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
)

from sepolicy.cil_policy import parse_cil_lines
from sepolicy.classmap import Classmap
from sepolicy.contexts import (
    ContextsType,
    parse_contexts_texts,
    parse_genfs_contexts,
)
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
from sepolicy.merge import add_mergeable_rule, merge_current_rules
from sepolicy.policy import (
    Policy,
    PolicyMetadata,
    PolicyName,
    PolicyParseFormat,
    PolicySourceOrigin,
    PolicyType,
    get_policy_type_by_name,
)
from sepolicy.rule import Rule
from sepolicy.rule_container import RuleContainer
from sepolicy.rules import split_normalize_rules_text
from sepolicy.source_macros import SourceMacros
from sepolicy.source_rule import SourceRuleParser
from sepolicy.source_text import PolicyFileType, SourceText
from utils.frozendict import FrozenDict
from utils.utils import (
    android_root,
    read_texts,
    split_normalize_text,
)

system_sepolicy_path = Path(android_root, 'system/sepolicy')


def get_source_policy_path(version: str, current: bool):
    if current:
        return system_sepolicy_path

    return Path(system_sepolicy_path, f'prebuilts/api/{version}')


def read_source_contexts_text(rules_paths: List[Tuple[Path, PolicyName]]):
    contexts_paths: DefaultDict[ContextsType, List[Path]] = defaultdict(list)

    for file_path, policy_name in rules_paths:
        policy_type = get_policy_type_by_name(policy_name)
        assert isinstance(policy_type.origin, PolicySourceOrigin)

        contexts_name_map = policy_type.origin.contexts_name_map
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
    mergeable_rules: List[Rule] = []

    def add_rule(rule: Rule):
        add_mergeable_rule(rule, mergeable_rules, rules)

    parser = SourceRuleParser(
        add_rule,
        classmap,
    )
    for source_line in expanded_rules:
        parser.parse_line(source_line)

    merge_current_rules(mergeable_rules, rules)

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

    macros_name_rules = parse_macros(classmap, macros)

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


def __parse_source_cil_policies(
    policy_type: PolicyType,
    file_path: Path,
    metadata: PolicyMetadata,
    classmap: Optional[Classmap],
    verbose: bool,
):
    genfs_rules = RuleContainer()
    rules = RuleContainer(sparse_match=True)

    parse_cil_lines(
        file_path,
        rules,
        genfs_rules,
        conditional_types_map={},
        reference_conditional_types_maps=[],
        classmap=classmap,
        version=metadata.version,
        name=policy_type.pretty_name,
        verbose=verbose,
    )

    return Policy(
        policy_type.name,
        rules,
        genfs_rules=genfs_rules,
        contexts={},
        metadata=metadata,
    )


def parse_source_cil_policies(
    policy_type: PolicyType,
    metadata: PolicyMetadata,
    classmap: Optional[Classmap],
    current: bool,
    verbose: bool,
):
    assert isinstance(policy_type.origin, PolicySourceOrigin)

    cil_file_name = policy_type.origin.cil_file_name
    assert cil_file_name is not None

    sepolicy_path = get_source_policy_path(
        metadata.version,
        current,
    )
    source_cil_rules_path = Path(
        sepolicy_path,
        cil_file_name,
    )

    return __parse_source_cil_policies(
        policy_type,
        source_cil_rules_path,
        metadata,
        classmap,
        verbose=verbose,
    )


def parse_metadata_source_policies(
    rules_dir_paths: List[Tuple[Path, PolicyName]],
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
        policy_type.name,
        rules,
        genfs_rules=genfs_rules,
        contexts=contexts,
        metadata=metadata,
    )


class SourceIndex:
    def __init__(
        self,
        extra_rules_paths: Dict[Optional[PolicyName], List[Path]],
        extra_macros_paths: Dict[Optional[PolicyName], List[Path]],
        current: bool,
        verbose: bool,
    ):
        self.__extra_rules_paths = extra_rules_paths
        self.__extra_macros_paths = extra_macros_paths
        self.__current = current
        self.__verbose = verbose

        self.__source_index: DefaultDict[
            PolicyMetadata,
            Dict[PolicyName, Policy],
        ] = defaultdict(dict)

        self.__macro_dir_paths_index: Dict[
            Tuple[
                # version
                str,
                # policy name
                PolicyName,
            ],
            Tuple[Path, ...],
        ] = {}
        self.__classmap_index: Dict[
            Tuple[PolicyMetadata, Tuple[Path, ...]],
            Classmap,
        ] = {}
        self.__macros_source_text_index: Dict[
            Tuple[Path, ...],
            SourceText,
        ] = {}
        self.__macros_index: Dict[
            Tuple[PolicyMetadata, Tuple[Path, ...]],
            SourceMacros,
        ] = {}

    def __get_policy_dir_paths(
        self,
        policy_type: PolicyType,
        version: str,
        macros: bool,
    ):
        assert isinstance(policy_type.origin, PolicySourceOrigin)
        dir_paths: List[Tuple[Path, PolicyName]] = []

        def add_subdirs(subdirs: Tuple[Tuple[str, bool], ...]):
            for subdir, versioned in subdirs:
                current = self.__current
                if not versioned:
                    current = True

                source_policy_path = get_source_policy_path(version, current)
                dir_path = Path(source_policy_path, subdir)
                if not dir_path.exists():
                    continue

                dir_paths.append((dir_path, policy_type.name))

        if macros and policy_type.origin.macros_subdirs is not None:
            add_subdirs(policy_type.origin.macros_subdirs)
        elif not macros and policy_type.origin.rules_subdirs is not None:
            add_subdirs(policy_type.origin.rules_subdirs)

        if macros:
            extras = self.__extra_macros_paths
        else:
            extras = self.__extra_rules_paths

        def add_extras(policy_name: Optional[PolicyName]):
            if policy_name not in extras:
                return

            dir_paths.extend((e, policy_type.name) for e in extras[policy_name])

        add_extras(None)
        add_extras(policy_type.name)

        return dir_paths

    def __get_policy_all_paths(
        self,
        policy_type: PolicyType,
        version: str,
        macros: bool,
    ):
        assert isinstance(policy_type.origin, PolicySourceOrigin)

        dir_paths: List[Tuple[Path, PolicyName]] = []

        if macros:
            # flagging_macros are not versioned and must always be loaded
            dir_path = Path(system_sepolicy_path, 'flagging')
            dir_paths.append((dir_path, policy_type.name))

        sources = None
        if macros and policy_type.origin.macro_sources:
            sources = policy_type.origin.macro_sources
        elif not macros and policy_type.origin.rule_sources:
            sources = policy_type.origin.rule_sources

        if sources is not None:
            for source_name in sources:
                source_policy_type = get_policy_type_by_name(source_name)
                source_macro_paths = self.__get_policy_dir_paths(
                    source_policy_type,
                    version,
                    macros,
                )
                dir_paths.extend(source_macro_paths)

        own_dir_paths = self.__get_policy_dir_paths(
            policy_type,
            version,
            macros,
        )
        dir_paths.extend(own_dir_paths)

        return dir_paths

    def __get_policy_key_paths(
        self,
        policy_type: PolicyType,
        version: str,
        macros: bool,
    ):
        dir_paths = self.__get_policy_all_paths(policy_type, version, macros)
        return tuple(v[0] for v in dir_paths)

    def __get_macro_dir_paths(
        self,
        metadata: PolicyMetadata,
        policy_name: PolicyName,
    ):
        key = (metadata.version, policy_name)

        macro_dir_paths = self.__macro_dir_paths_index.get(key)
        if macro_dir_paths is not None:
            return macro_dir_paths

        policy_type = get_policy_type_by_name(policy_name)
        macro_dir_paths = self.__get_policy_key_paths(
            policy_type,
            version=metadata.version,
            macros=True,
        )

        self.__macro_dir_paths_index[key] = macro_dir_paths

        return macro_dir_paths

    def __get_macros_source_text(
        self,
        metadata: PolicyMetadata,
        policy_name: PolicyName,
    ):
        macro_dir_paths = self.__get_macro_dir_paths(metadata, policy_name)

        source_text = self.__macros_source_text_index.get(macro_dir_paths)
        if source_text is not None:
            return source_text

        source_text = SourceText()
        source_text.load_texts(
            macro_dir_paths,
            disallowed_types={PolicyFileType.TE},
        )
        self.__macros_source_text_index[macro_dir_paths] = source_text

        return source_text

    def __get_classmap(
        self,
        metadata: PolicyMetadata,
        policy_name: PolicyName,
    ):
        source_text = self.__get_macros_source_text(metadata, policy_name)

        access_vectors_path = source_text.get_path(
            PolicyFileType.ACCESS_VECTORS,
        )
        flagging_macros_path = source_text.get_path(
            PolicyFileType.FLAGGING_MACROS,
        )

        key = (
            metadata,
            (
                access_vectors_path,
                flagging_macros_path,
            ),
        )
        classmap = self.__classmap_index.get(key)
        if classmap is not None:
            return classmap

        classmap = parse_source_classmap(
            source_text.get_text(PolicyFileType.FLAGGING_MACROS),
            source_text.get_text(PolicyFileType.ACCESS_VECTORS),
            metadata,
            verbose=self.__verbose,
        )
        self.__classmap_index[key] = classmap

        return classmap

    def __parse_macros(
        self,
        metadata: PolicyMetadata,
        policy_name: PolicyName,
    ):
        if self.__verbose:
            print(f'Loading macros for metadata version: {metadata.version}')
            print('Variables:')
            for k, v in metadata.variables.items():
                print(f'{k}={v}')

        macro_dir_paths = self.__get_macro_dir_paths(metadata, policy_name)
        source_text = self.__get_macros_source_text(metadata, policy_name)
        classmap = self.__get_classmap(metadata, policy_name)

        key = (metadata, macro_dir_paths)
        macros = self.__macros_index.get(key)
        if macros is not None:
            return source_text, classmap, macros

        macros = parse_source_macros(
            source_text,
            metadata.variables,
            classmap,
            verbose=self.__verbose,
        )
        self.__macros_index[key] = macros

        print(f'Found macros:\n{macros}')

        return source_text, classmap, macros

    def get_macros(self, metadata: PolicyMetadata, policy_name: PolicyName):
        _, _, macros = self.__parse_macros(metadata, policy_name)
        return macros

    def get_macros_source_text(
        self,
        metadata: PolicyMetadata,
        policy_name: PolicyName,
    ):
        source_text, _, _ = self.__parse_macros(metadata, policy_name)
        return source_text

    def get_classmap(self, metadata: PolicyMetadata, policy_name: PolicyName):
        _, classmap, _ = self.__parse_macros(metadata, policy_name)
        return classmap

    def get_source_index(self, metadata: PolicyMetadata):
        return self.__source_index[metadata]

    def parse_source_policy(
        self,
        metadata: PolicyMetadata,
        policy_name: PolicyName,
    ):
        if policy_name in self.__source_index[metadata]:
            return self.__source_index[metadata][policy_name]

        policy_type = get_policy_type_by_name(policy_name)

        if self.__verbose:
            print(
                f'Loading {policy_type.pretty_name} for metadata version: '
                f'{metadata.version}'
            )
            print('Variables:')
            for k, v in metadata.variables.items():
                print(f'{k}={v}')

        assert isinstance(policy_type.origin, PolicySourceOrigin)

        if policy_type.origin.format == PolicyParseFormat.CIL:
            policy = parse_source_cil_policies(
                policy_type,
                metadata,
                classmap=None,
                current=self.__current,
                verbose=self.__verbose,
            )
        else:
            rules_dir_paths = self.__get_policy_all_paths(
                policy_type,
                version=metadata.version,
                macros=False,
            )

            source_text = self.get_macros_source_text(metadata, policy_name)

            # Avoid mutating the original source text which might end up being
            # used by other policies
            source_text = source_text.copy()

            classmap = self.get_classmap(metadata, policy_name)

            policy = parse_metadata_source_policies(
                rules_dir_paths,
                policy_type,
                metadata,
                source_text,
                classmap,
                verbose=self.__verbose,
            )

        print(f'Found policy: {policy}')

        self.__source_index[metadata][policy_name] = policy

        return policy

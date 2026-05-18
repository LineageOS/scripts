# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from collections import defaultdict
from dataclasses import astuple, dataclass
from pathlib import Path
from typing import DefaultDict, Dict, List, Optional, Set, Tuple

from sepolicy.cil_rule import CilRule, unpack_cil_line
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
from sepolicy.policy import (
    Policy,
    PolicyMetadata,
    PolicyName,
    PolicyParseFormat,
    PolicySourceOrigin,
    PolicyType,
    get_policy_types_by_origin,
)
from sepolicy.rule import Rule
from sepolicy.rule_container import RuleContainer
from sepolicy.rules import split_normalize_rules_text
from sepolicy.source_rule import SourceRule
from sepolicy.varargs import Ioctls
from utils.frozendict import FrozenDict
from utils.utils import (
    android_root,
    read_texts,
    resolve_paths,
    split_normalize_text,
)

system_sepolicy_path = Path(android_root, 'system/sepolicy')


def get_source_policy_path(version: str, current: bool):
    if current:
        return system_sepolicy_path

    return Path(system_sepolicy_path, f'prebuilts/api/{version}')


@dataclass
class SourceMacrosText:
    flagging_macros: str
    ioctl_defines: str
    nlmsg_defines: str
    ioctl_macros: str
    nlmsg_macros: str
    macros: str


@dataclass
class SourceMacros:
    class_perms: Dict[str, List[Tuple[str, Set[str]]]]
    class_sets: List[Tuple[str, Set[str]]]
    ioctls: List[Tuple[str, Ioctls]]
    nlmsgs: List[Tuple[str, Ioctls]]
    ioctl_defines: Dict[int, str]
    nlmsg_defines: Dict[int, str]
    macros_name_rules: List[Tuple[str, List[Rule]]]

    def __repr__(self):
        perms = set(t[0] for perms in self.class_perms.values() for t in perms)

        return (
            f'perms: {len(perms)}\n'
            f'class sets: {len(self.class_sets)}\n'
            f'ioctls: {len(self.ioctls)}\n'
            f'nlmsgs: {len(self.nlmsgs)}\n'
            f'ioctl defines: {len(self.ioctl_defines)}\n'
            f'nlmsg defines: {len(self.nlmsg_defines)}\n'
            f'macros: {len(self.macros_name_rules)}\n'
        )


@dataclass
class Source:
    macros: SourceMacros
    classmap: Classmap
    policy_index: Dict[PolicyName, Policy]


MACRO_FILES = [
    'global_macros',
    'neverallow_macros',
    'te_macros',
    # TODO: avoid rules parsing from re-parsing attributes every time...
    'attributes',
]
IOCTL_DEFINES_FILE = 'ioctl_defines'
IOCTL_MACROS_FILE = 'ioctl_macros'
NLMSG_DEFINES_FILE = 'nlmsg_defines'
NLMSG_MACROS_FILE = 'nlmsg_macros'


def read_source_macros_text(
    extra_macros_paths: List[Path],
    version: str,
    current: bool,
    verbose: bool,
):
    sepolicy_path = get_source_policy_path(version, current)

    def _resolve_paths(names: List[str]):
        system_paths = [Path(sepolicy_path, 'public', n) for n in names]

        return system_paths + resolve_paths(
            extra_macros_paths,
            names=set(names),
            recursive=True,
            paths_name='macros',
            verbose=verbose,
        )

    return SourceMacrosText(
        macros=read_texts(_resolve_paths(MACRO_FILES)),
        ioctl_defines=read_texts(_resolve_paths([IOCTL_DEFINES_FILE])),
        nlmsg_defines=read_texts(_resolve_paths([NLMSG_DEFINES_FILE])),
        ioctl_macros=read_texts(_resolve_paths([IOCTL_MACROS_FILE])),
        nlmsg_macros=read_texts(_resolve_paths([NLMSG_MACROS_FILE])),
        flagging_macros=read_texts(
            [
                Path(
                    # These do not exist per-version
                    system_sepolicy_path,
                    'flagging',
                    'flagging_macros',
                )
            ],
        ),
    )


def read_source_rules_text(
    extra_rules_paths: List[Path],
    policy_type: PolicyType,
    subdir: Optional[str],
    version: str,
    current: bool,
    verbose: bool,
):
    sepolicy_path = get_source_policy_path(version, current)
    names = {'*.te', 'attributes'}

    source_paths = []
    if subdir:
        source_paths = resolve_paths(
            [Path(sepolicy_path, subdir)],
            names=names,
            recursive=False,
            paths_name=f'{policy_type.pretty_name} rules',
            verbose=verbose,
        )

    return read_texts(
        source_paths
        + resolve_paths(
            extra_rules_paths,
            names=names,
            recursive=True,
            paths_name=f'{policy_type.pretty_name} rules',
            verbose=verbose,
        )
    )


def read_source_contexts_text(
    extra_rules_paths: List[Path],
    origin: PolicySourceOrigin,
    version: str,
    current: bool,
    name: str,
    verbose: bool,
):
    sepolicy_path = get_source_policy_path(version, current)

    def _source_paths(context_name: str):
        source_paths = []

        if origin.subdir:
            source_paths = resolve_paths(
                [Path(sepolicy_path, origin.subdir)],
                names={context_name},
                recursive=False,
                paths_name=f'{name} {context_name}',
                verbose=verbose,
            )

        return source_paths

    contexts = {
        context_type: read_texts(
            _source_paths(context_name)
            + resolve_paths(
                extra_rules_paths,
                names={context_name},
                recursive=True,
                paths_name=f'{name} {context_name}',
                verbose=verbose,
            )
        )
        for context_type, context_name in origin.contexts_name_map.items()
    }

    return contexts


def parse_source_rules(
    rules_text: str,
    source_macros_text: SourceMacrosText,
    variables: FrozenDict[str, str],
    classmap: Classmap,
    verbose: bool,
):
    expanded_rules = expand_macro_calls_and_split(
        text=rules_text,
        environment_texts=list(astuple(source_macros_text)),
        variables=variables,
        split_fn=split_normalize_rules_text,
        map_fn=rule_body,
        preserve_macros=False,
        text_name='expanded_rules',
        verbose=verbose,
    )

    rules = RuleContainer()

    def add_rule(rule: Rule):
        rules.add(rule)

    for source_line in expanded_rules:
        SourceRule.from_line(
            source_line,
            add_rule=add_rule,
            classmap=classmap,
        )

    return rules


def parse_source_contexts(
    contexts_text: Dict[ContextsType, str],
    source_macros_text: SourceMacrosText,
    variables: FrozenDict[str, str],
    verbose: bool,
):
    expanded_contexts = {
        context_type: expand_macro_calls_and_split(
            text=context_text,
            environment_texts=[
                source_macros_text.flagging_macros,
            ],
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
    source_macros_text: SourceMacrosText,
    variables: FrozenDict[str, str],
    classmap: Classmap,
    verbose: bool,
):
    base_environment_texts = [
        source_macros_text.flagging_macros,
    ]

    macros_environment_texts = [
        source_macros_text.flagging_macros,
        source_macros_text.ioctl_defines,
        source_macros_text.ioctl_macros,
        source_macros_text.nlmsg_defines,
        source_macros_text.nlmsg_macros,
    ]

    ioctl_defines = expand_macro_calls_and_split(
        text=source_macros_text.ioctl_defines,
        environment_texts=base_environment_texts,
        variables=variables,
        split_fn=split_normalize_rules_text,
        map_fn=macro_name_body,
        preserve_macros=True,
        text_name='ioctl_defines',
        verbose=verbose,
    )

    nlmsg_defines = expand_macro_calls_and_split(
        text=source_macros_text.nlmsg_defines,
        environment_texts=base_environment_texts,
        variables=variables,
        split_fn=split_normalize_rules_text,
        map_fn=macro_name_body,
        preserve_macros=True,
        text_name='nlmsg_defines',
        verbose=verbose,
    )

    ioctl_macros = expand_macro_calls_and_split(
        text=source_macros_text.ioctl_macros,
        environment_texts=[
            source_macros_text.flagging_macros,
            source_macros_text.ioctl_defines,
        ],
        variables=variables,
        split_fn=split_normalize_rules_text,
        map_fn=macro_name_body,
        preserve_macros=True,
        text_name='ioctl_macros',
        verbose=verbose,
    )

    nlmsg_macros = expand_macro_calls_and_split(
        text=source_macros_text.nlmsg_macros,
        environment_texts=[
            source_macros_text.flagging_macros,
            source_macros_text.nlmsg_defines,
        ],
        variables=variables,
        split_fn=split_normalize_rules_text,
        map_fn=macro_name_body,
        preserve_macros=True,
        text_name='nlmsg_macros',
        verbose=verbose,
    )

    expanded_macros = expand_macro_calls_and_split(
        text=source_macros_text.macros,
        environment_texts=macros_environment_texts,
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
    source_macros_text: SourceMacrosText,
    metadata: PolicyMetadata,
    current: bool,
    verbose: bool,
):
    versioned_system_sepolicy_path = get_source_policy_path(
        metadata.version,
        current,
    )

    access_vectors = read_texts(
        [
            Path(
                versioned_system_sepolicy_path,
                'private',
                'access_vectors',
            )
        ]
    )

    classmap_text = expand_macro_calls(
        [access_vectors],
        [source_macros_text.flagging_macros],
        metadata.variables,
        preserve_macros=True,
        text_name='access_vectors',
        verbose=verbose,
    )

    return Classmap(classmap_text)


def parse_source_cil_rules(
    origin: PolicySourceOrigin,
    version: str,
    current: bool,
):
    assert origin.cil_file_name is not None

    sepolicy_path = get_source_policy_path(version, current)
    source_cil_rules_path = Path(
        sepolicy_path,
        origin.subdir or '',
        origin.cil_file_name,
    )
    rules = RuleContainer()

    def add_rule(rule: Rule):
        rules.add(rule)

    for line in source_cil_rules_path.read_text().splitlines():
        parts = unpack_cil_line(line)
        if parts is None:
            continue

        CilRule.from_line(
            line,
            parts,
            conditional_types_map={},
            reference_conditional_types_maps=[],
            add_rule=add_rule,
            add_genfs_rule=None,
            version=None,
        )

    return rules


def parse_metadata_source_policies(
    extra_rules_paths: List[Path],
    policy_type: PolicyType,
    metadata: PolicyMetadata,
    source_macros_text: SourceMacrosText,
    classmap: Classmap,
    current: bool,
    verbose: bool,
):
    assert isinstance(policy_type.origin, PolicySourceOrigin)

    if policy_type.origin.format == PolicyParseFormat.CIL:
        rules = parse_source_cil_rules(
            policy_type.origin,
            metadata.version,
            current,
        )

        return Policy(
            policy_type.name,
            rules,
            genfs_rules=RuleContainer(),
            contexts={},
            metadata=metadata,
        )

    rules_text = read_source_rules_text(
        extra_rules_paths,
        policy_type,
        subdir=policy_type.origin.subdir,
        version=metadata.version,
        current=current,
        verbose=verbose,
    )

    contexts_text = read_source_contexts_text(
        extra_rules_paths,
        policy_type.origin,
        version=metadata.version,
        current=current,
        name=policy_type.pretty_name,
        verbose=verbose,
    )

    rules = parse_source_rules(
        rules_text,
        source_macros_text,
        metadata.variables,
        classmap,
        verbose=verbose,
    )

    contexts, genfs_rules = parse_source_contexts(
        contexts_text,
        source_macros_text,
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
        extra_rules_paths: List[Path],
        extra_macros_paths: List[Path],
        current: bool,
        verbose: bool,
    ):
        self.__extra_rules_paths = extra_rules_paths
        self.__extra_macros_paths = extra_macros_paths
        self.__current = current
        self.__verbose = verbose

        self.__version_macros_text_map: Dict[str, SourceMacrosText] = {}
        self.__source_index: DefaultDict[PolicyMetadata, Source] = defaultdict()

    def __load_texts(self, version: str):
        if version in self.__version_macros_text_map:
            return self.__version_macros_text_map[version]

        version_macros_text = read_source_macros_text(
            self.__extra_macros_paths,
            version,
            self.__current,
            self.__verbose,
        )
        self.__version_macros_text_map[version] = version_macros_text

        return version_macros_text

    def get_source_policy(self, metadata: PolicyMetadata):
        if metadata in self.__source_index:
            return self.__source_index[metadata]

        if self.__verbose:
            print(
                f'Loading source policies for metadata version: '
                f'{metadata.version}'
            )
            print('Variables:')
            for k, v in metadata.variables.items():
                print(f'{k}={v}')

        source_macros_text = self.__load_texts(metadata.version)

        classmap = parse_source_classmap(
            source_macros_text,
            metadata,
            current=self.__current,
            verbose=self.__verbose,
        )

        macros = parse_source_macros(
            source_macros_text,
            metadata.variables,
            classmap,
            verbose=self.__verbose,
        )

        print(f'Found macros:\n{macros}')

        policy_index: Dict[PolicyName, Policy] = {}
        for policy_type in get_policy_types_by_origin(PolicySourceOrigin):
            assert isinstance(policy_type.origin, PolicySourceOrigin)

            policy = parse_metadata_source_policies(
                self.__extra_rules_paths,
                policy_type,
                metadata,
                source_macros_text,
                classmap,
                current=self.__current,
                verbose=self.__verbose,
            )

            policy_index[policy_type.name] = policy

            print(f'Found policy: {policy}')

        source = Source(
            macros,
            classmap,
            policy_index,
        )

        self.__source_index[metadata] = source

        return source

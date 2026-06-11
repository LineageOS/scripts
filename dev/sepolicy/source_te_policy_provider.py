# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path
from typing import (
    Dict,
    List,
    Optional,
    Tuple,
)

from sepolicy.classmap import Classmap
from sepolicy.policy import (
    PolicyIndex,
    PolicyMetadata,
    PolicyProvider,
    PolicySourceOrigin,
    PolicyType,
    get_policy_type_by_name,
)
from sepolicy.source_macros import SourceMacros
from sepolicy.source_policy import (
    get_source_policy_path,
    parse_metadata_source_policies,
    parse_source_classmap,
    parse_source_macros,
    system_sepolicy_path,
)
from sepolicy.source_text import PolicyFileType, SourceText


class SourceTePolicyProvider(PolicyProvider):
    def __init__(
        self,
        extra_rules_paths: Dict[Optional[str], List[Path]],
        extra_macros_paths: Dict[Optional[str], List[Path]],
        current: bool,
        verbose: bool,
    ):
        super().__init__(PolicySourceOrigin)

        self.__extra_rules_paths = extra_rules_paths
        self.__extra_macros_paths = extra_macros_paths
        self.__current = current
        self.__verbose = verbose

        self.__macro_dir_paths_index: Dict[
            Tuple[
                # version
                str,
                # policy name
                str,
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
        dir_paths: List[Tuple[Path, str]] = []

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

        def add_extras(policy_name: Optional[str]):
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

        dir_paths: List[Tuple[Path, str]] = []

        if macros:
            # flagging_macros are not versioned and must always be loaded
            dir_path = Path(system_sepolicy_path, 'flagging')
            dir_paths.append((dir_path, policy_type.name))

        sources = None
        if macros and policy_type.origin.macro_sources:
            sources = policy_type.origin.macro_sources

        if sources is not None:
            for source_policy_type in sources:
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
        policy_name: str,
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
        policy_name: str,
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
        policy_name: str,
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
        policy_name: str,
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

    def get_macros(self, metadata: PolicyMetadata, policy_name: str):
        _, _, macros = self.__parse_macros(metadata, policy_name)
        return macros

    def get_macros_source_text(
        self,
        metadata: PolicyMetadata,
        policy_name: str,
    ):
        source_text, _, _ = self.__parse_macros(metadata, policy_name)
        return source_text

    def get_classmap(self, metadata: PolicyMetadata, policy_name: str):
        _, classmap, _ = self.__parse_macros(metadata, policy_name)
        return classmap

    def get_policy(
        self,
        policy_index: PolicyIndex,
        policy_type: PolicyType,
        metadata: Optional[PolicyMetadata] = None,
    ):
        assert metadata is not None

        if self.__verbose:
            print(
                f'Loading {policy_type.pretty_name} for metadata version: '
                f'{metadata.version}'
            )
            print('Variables:')
            for k, v in metadata.variables.items():
                print(f'{k}={v}')

        assert isinstance(policy_type.origin, PolicySourceOrigin)

        rules_dir_paths = self.__get_policy_all_paths(
            policy_type,
            version=metadata.version,
            macros=False,
        )

        source_text = self.get_macros_source_text(metadata, policy_type.name)

        # Avoid mutating the original source text which might end up being
        # used by other policies
        source_text = source_text.copy()

        classmap = self.get_classmap(metadata, policy_type.name)

        policy = parse_metadata_source_policies(
            rules_dir_paths,
            policy_type,
            metadata,
            source_text,
            classmap,
            verbose=self.__verbose,
        )

        policy.macros = self.get_macros(metadata, policy_type.name)

        return policy

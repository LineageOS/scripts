# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import DefaultDict, Dict, List, Optional, Set, Tuple, cast


class PolicyFileType(IntEnum):
    FLAGGING_MACROS = 0
    SECURITY_CLASSES = 1
    INITIAL_SIDS = 2
    ACCESS_VECTORS = 3
    GLOBAL_MACROS = 4
    NEVERALLOW_MACROS = 5
    MLS_MACROS = 6
    MLS_DECL = 7
    MLS = 8
    POLICY_CAPABILITIES = 9
    TE_MACROS = 10
    IOCTL_DEFINES = 11
    IOCTL_MACROS = 12
    NLMSG_DEFINES = 13
    NLMSG_MACROS = 14
    ATTRIBUTES = 15
    TE = 16
    ROLES_DECL = 17
    ROLES = 18
    USERS = 19
    INITIAL_SID_CONTEXTS = 20
    FS_USE = 21
    GENFS_CONTEXTS = 22
    PORT_CONTEXTS = 23
    OTHER_CONTEXTS = 24


POLICY_ORDER_MAP = {
    'flagging_macros': PolicyFileType.FLAGGING_MACROS,
    'security_classes': PolicyFileType.SECURITY_CLASSES,
    'initial_sids': PolicyFileType.INITIAL_SIDS,
    'access_vectors': PolicyFileType.ACCESS_VECTORS,
    'global_macros': PolicyFileType.GLOBAL_MACROS,
    'neverallow_macros': PolicyFileType.NEVERALLOW_MACROS,
    'mls_macros': PolicyFileType.MLS_MACROS,
    'mls_decl': PolicyFileType.MLS_DECL,
    'mls': PolicyFileType.MLS,
    'policy_capabilities': PolicyFileType.POLICY_CAPABILITIES,
    'te_macros': PolicyFileType.TE_MACROS,
    'ioctl_defines': PolicyFileType.IOCTL_DEFINES,
    'ioctl_macros': PolicyFileType.IOCTL_MACROS,
    'nlmsg_defines': PolicyFileType.NLMSG_DEFINES,
    'nlmsg_macros': PolicyFileType.NLMSG_MACROS,
    'attributes': PolicyFileType.ATTRIBUTES,
    'roles_decl': PolicyFileType.ROLES_DECL,
    'roles': PolicyFileType.ROLES,
    'users': PolicyFileType.USERS,
    'initial_sid_contexts': PolicyFileType.INITIAL_SID_CONTEXTS,
    'fs_use': PolicyFileType.FS_USE,
    'genfs_contexts': PolicyFileType.GENFS_CONTEXTS,
    'port_contexts': PolicyFileType.PORT_CONTEXTS,
}


@dataclass
class SourceText:
    paths: DefaultDict[int, List[Path]] = field(
        default_factory=lambda: cast(
            DefaultDict[int, List[Path]],
            defaultdict(list),
        )
    )
    texts: Dict[Path, str] = field(
        default_factory=lambda: cast(
            Dict[Path, str],
            dict(),
        )
    )

    def copy(self):
        return SourceText(
            defaultdict(list, {k: v.copy() for k, v in self.paths.items()}),
            dict(self.texts),
        )

    def update(
        self,
        other: SourceText,
        allowed_types: Optional[Set[PolicyFileType]] = None,
        disallowed_types: Optional[Set[PolicyFileType]] = None,
    ):
        for order, paths in other.paths.items():
            if allowed_types is not None and order not in allowed_types:
                continue

            if disallowed_types is not None and order in disallowed_types:
                continue

            for path in paths:
                # texts is keyed by path, so a repeated path is the same file
                if path in self.texts:
                    continue

                self.paths[order].append(path)
                self.texts[path] = other.texts[path]

    def __policy_type(self, policy_path: Path):
        if policy_path.name.endswith('.te'):
            return PolicyFileType.TE

        return POLICY_ORDER_MAP.get(policy_path.stem)

    def __add_path(
        self,
        policy_path: Path,
        allowed_types: Optional[Set[PolicyFileType]] = None,
        disallowed_types: Optional[Set[PolicyFileType]] = None,
    ):
        order = self.__policy_type(policy_path)
        if order is None:
            return

        if allowed_types is not None and order not in allowed_types:
            return

        if disallowed_types is not None and order in disallowed_types:
            return

        text = policy_path.read_text()
        self.texts[policy_path] = text
        self.paths[order].append(policy_path)

    def load_texts(
        self,
        dir_paths: Tuple[Path, ...],
        allowed_types: Optional[Set[PolicyFileType]] = None,
        disallowed_types: Optional[Set[PolicyFileType]] = None,
    ):
        for dir_path in dir_paths:
            assert dir_path.is_dir(), f'{dir_path} is not a directory'

            for file_path in sorted(dir_path.iterdir()):
                if not file_path.is_file():
                    continue

                self.__add_path(
                    file_path,
                    allowed_types=allowed_types,
                    disallowed_types=disallowed_types,
                )

    def get_texts(self, types: Optional[Set[PolicyFileType]] = None):
        all_texts: List[str] = []

        for t in sorted(self.paths):
            if types is not None and t not in types:
                continue

            all_texts.extend(self.texts[p] for p in self.paths[t])

        return all_texts

    def get_text(self, t: PolicyFileType):
        texts = self.get_texts({t})
        assert len(texts) == 1
        return next(iter(texts))

    def get_path(self, t: PolicyFileType):
        file_paths = self.paths[t]
        assert len(file_paths) == 1
        return next(iter(file_paths))

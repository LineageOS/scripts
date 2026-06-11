# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass
from typing import (
    Dict,
    List,
    Set,
    Tuple,
)

from sepolicy.rule import Rule
from sepolicy.varargs import Ioctls


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

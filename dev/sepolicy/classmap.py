# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, List

SELINUX_INCLUDE_PATH = 'security/selinux/include/'
SCRIPT_PATH = Path(__file__).parent.resolve()
CLASSMAP_GENERATOR_C_PATH = Path(SCRIPT_PATH, 'classmap_generator.c')


def extract_classmap(selinux_include_path: str):
    with TemporaryDirectory() as tmp_path:
        classmap_generator_path = Path(tmp_path, 'classmap_generator')

        subprocess.check_call(
            [
                'gcc',
                '-I',
                selinux_include_path,
                CLASSMAP_GENERATOR_C_PATH,
                '-o',
                classmap_generator_path,
            ]
        )

        program_output = subprocess.check_output(
            [
                classmap_generator_path,
            ]
        )
        return json.loads(program_output)


class Classmap:
    def __init__(self, selinux_include_path: str):
        class_perms_map = extract_classmap(selinux_include_path)

        self.__class_index_map: Dict[str, int] = {}
        self.__class_perms_index_map: Dict[str, Dict[str, int]] = {}

        for index, class_name in enumerate(class_perms_map.keys()):
            self.__class_index_map[class_name] = index

            for perm_index, perm_name in enumerate(class_perms_map[class_name]):
                self.__class_perms_index_map.setdefault(class_name, {})
                self.__class_perms_index_map[class_name][perm_name] = perm_index

    def class_types(self, t: str):
        for key in self.__class_index_map:
            if key.endswith(t):
                yield key

    def class_perms(self, class_name: str):
        return list(self.__class_perms_index_map[class_name].keys())

    def class_index(self, class_name: str):
        default = len(self.__class_index_map)
        return self.__class_index_map.get(class_name, default)

    def perm_index(self, class_name: str, perm_name: str):
        if class_name not in self.__class_index_map:
            return 0

        perms_map = self.__class_perms_index_map[class_name]

        if perm_name not in perms_map:
            return len(perms_map)

        return perms_map[perm_name]

    def sort_classes(self, classes: List[str]):
        classes.sort(key=lambda c: self.class_index(c))

    def sort_perms(self, class_name: str, perms: List[str]):
        if perms == ['*']:
            perms[:] = self.class_perms(class_name)
            return

        # Remove duplicates
        perms[:] = list(dict.fromkeys(perms))

        perms.sort(key=lambda p: self.perm_index(class_name, p))

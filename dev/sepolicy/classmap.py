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


def extract_classmap(selinux_include_path: str) -> Dict[str, List[str]]:
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
        self.__class_perms_map = extract_classmap(selinux_include_path)

    def class_types(self, t: str):
        for key in self.__class_perms_map:
            if key.endswith(t):
                yield key

    def class_perms(self, class_name: str):
        return self.__class_perms_map[class_name]

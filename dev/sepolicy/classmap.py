# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from utils.utils import split_normalize_text


def extract_classmap(
    flagging_macros_path: Optional[Path],
    version: str,
    access_vectors_path: Path,
) -> Dict[str, List[str]]:
    text = access_vectors_path.read_text()

    if flagging_macros_path is not None:
        input_text = flagging_macros_path.read_text()
        input_text += text
        # TODO: unify this with macro processing
        text = subprocess.check_output(
            ['m4', '-D', f'target_board_api_level={version}'],
            input=input_text,
            text=True,
        )

    lines = split_normalize_text(text)
    text = ''.join(lines)
    tokens = text.split()

    classes_map: Dict[str, List[str]] = {}
    commons_map: Dict[str, List[str]] = {}

    i = 0
    while i < len(tokens):
        if tokens[i] == 'common':
            i += 1
            is_common = True
        elif tokens[i] == 'class':
            i += 1
            is_common = False
        else:
            assert False

        name = tokens[i]
        i += 1

        perms: List[str] = []

        if tokens[i] == 'inherits':
            i += 1

            assert not is_common

            inherit_name = tokens[i]
            i += 1

            inherited_perms = commons_map[inherit_name]
            perms.extend(inherited_perms)

        if tokens[i] == '{':
            i += 1
            while tokens[i] != '}':
                perms.append(tokens[i])
                i += 1
            i += 1

        if is_common:
            assert name not in commons_map
            commons_map[name] = perms
        else:
            assert name not in classes_map
            classes_map[name] = perms

    return classes_map


class Classmap:
    def __init__(
        self,
        flagging_macros_path: Optional[Path],
        version: str,
        access_vectors_path: Path,
    ):
        self.__class_perms_map = extract_classmap(
            flagging_macros_path,
            version,
            access_vectors_path,
        )

    def class_types(self, t: str):
        for key in self.__class_perms_map:
            if key.endswith(t):
                yield key

    def class_perms(self, class_name: str):
        return self.__class_perms_map[class_name][:]

# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
from enum import Enum
from os import path
from subprocess import PIPE, run
from typing import Dict, List

from lxml import etree

script_dir = path.dirname(path.realpath(__file__))
android_root = path.realpath(path.join(script_dir, '..', '..', '..'))


def get_files_with_name(dir_path: str, name: str):
    for subdir_path, _, file_names in os.walk(dir_path):
        for file_name in file_names:
            if file_name != name:
                continue

            android_bp_path = path.join(subdir_path, file_name)
            if not path.isfile(android_bp_path):
                continue

            yield android_bp_path


def get_dirs_with_file(dir_path: str, name: str):
    for file_path in get_files_with_name(dir_path, name):
        yield path.dirname(file_path)


def run_cmd(cmd: List[str]):
    proc = run(
        cmd,
        stdout=PIPE,
        stderr=PIPE,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        cmd_str = ' '.join(cmd)
        s = f'Failed to run command "{cmd_str}":\n'
        s += f'stdout:\n{proc.stdout}\n'
        s += f'stderr:\n{proc.stderr}\n'
        raise ValueError(s)
    return proc.stdout


class Color(str, Enum):
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    END = '\033[0m'


def color_print(*args, color: Color, **kwargs):
    args_str = ' '.join(str(arg) for arg in args)
    args_str = color.value + args_str + Color.END.value
    print(args_str, **kwargs)


def xml_element_canonical_str(element: etree.Element):
    return etree.tostring(element, method='c14n', exclusive=True)


XML_COMMENT_TEXT = """
     SPDX-FileCopyrightText: The LineageOS Project
     SPDX-License-Identifier: Apache-2.0
"""

XML_COMMENT = f"""
<!--{XML_COMMENT_TEXT}-->
"""

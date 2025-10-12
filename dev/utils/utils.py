# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
from contextlib import contextmanager
from enum import Enum
from os import path
from subprocess import PIPE, run
from typing import Generator, List, Optional, Set

script_dir = path.dirname(path.realpath(__file__))
android_root = path.realpath(path.join(script_dir, '..', '..', '..', '..'))


def get_files_with_name(
    dir_path: str,
    name: str,
    skipped_directory_names: Optional[Set[str]] = None,
):
    for subdir_path, dir_names, file_names in os.walk(dir_path):
        if skipped_directory_names is not None:
            dir_names[:] = list(
                filter(lambda n: n not in skipped_directory_names, dir_names)
            )

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


def run_cmd(cmd: List[str], capture: bool=True):
    if capture:
        stdout = PIPE
        stderr = PIPE
    else:
        stdout = None
        stderr = None

    proc = run(
        cmd,
        stdout=stdout,
        stderr=stderr,
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


def color_print(*args: object, color: Color):
    args_str = ' '.join(str(arg) for arg in args)
    args_str = color.value + args_str + Color.END.value
    print(args_str)


def remove_comments(line: str):
    index = line.find('#')
    if index != -1:
        line = line[:index]

    return line


def is_empty_line(line: str):
    return not line.strip()


def split_normalize_text(text: str):
    lines = text.splitlines(keepends=True)
    lines = list(map(remove_comments, lines))
    lines = list(filter(lambda line: not is_empty_line(line), lines))
    return lines


@contextmanager
def WorkingDirectory(dir_path: str) -> Generator[None, None, None]:
    cwd = os.getcwd()

    os.chdir(dir_path)

    try:
        yield
    finally:
        os.chdir(cwd)

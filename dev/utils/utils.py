# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
import re
from contextlib import contextmanager
from enum import StrEnum
from fnmatch import fnmatch
from os import path
from pathlib import Path
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


def run_cmd(cmd: List[str], capture: bool = True):
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


class Color(StrEnum):
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    END = '\033[0m'


def color_print(*args: object, color: Color):
    args_str = ' '.join(str(arg) for arg in args)
    args_str = color.value + args_str + Color.END.value
    print(args_str)


def read_texts(text_file_paths: List[Path]):
    texts: List[str] = []
    for text_file_path in text_file_paths:
        text = text_file_path.read_text()
        texts.append(text)
        texts.append('\n')
    return ''.join(texts)


SPACE_RE = re.compile(r'[ \t]+')


def split_normalize_text(text: str):
    out: list[str] = []

    for line in text.splitlines(keepends=True):
        comment_index = line.find('#')

        if comment_index != -1:
            line = line[:comment_index]

        line = SPACE_RE.sub(' ', line.lstrip())

        if line.strip():
            out.append(line)

    return out

@contextmanager
def WorkingDirectory(dir_path: str) -> Generator[None, None, None]:
    cwd = os.getcwd()

    os.chdir(dir_path)

    try:
        yield
    finally:
        os.chdir(cwd)


def resolve_paths(
    dir_paths: List[Path],
    names: Set[str],
    recursive: bool,
    paths_name: str,
    verbose: bool,
):
    resolved_paths: List[Path] = []

    def add_path(mp: Path):
        if not mp.is_file():
            return

        for name in names:
            if mp.name == name or fnmatch(mp.name, name):
                break
        else:
            return

        if verbose:
            print(f'Loading {paths_name}: {mp}')

        resolved_paths.append(mp)

    for dir_path in dir_paths:
        if dir_path.is_file():
            add_path(dir_path)
            continue

        assert dir_path.is_dir(), f'{dir_path} is not a file or directory'

        if recursive:
            for root, _, files in dir_path.walk():
                for file in files:
                    file_path = root / file
                    add_path(file_path)
        else:
            for file_path in dir_path.iterdir():
                add_path(file_path)

    return resolved_paths

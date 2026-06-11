# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile

from utils.utils import (
    Color,
    android_root,
    color_print,
    run_cmd,
)

checkpolicy_rel_path = 'out/host/linux-x86/bin/checkpolicy'
checkpolicy_path = Path(android_root, checkpolicy_rel_path)
if not checkpolicy_path.exists():
    color_print(
        f'{checkpolicy_path} does not exist, run "m checkpolicy"',
        color=Color.RED,
    )
    exit(-1)


secilc_rel_path = 'out/host/linux-x86/bin/secilc'
secilc_path = Path(android_root, secilc_rel_path)
if not secilc_path.exists():
    color_print(
        f'{secilc_path} does not exist, run "m secilc"',
        color=Color.RED,
    )
    exit(-1)


@contextmanager
def _compiled_policy_path():
    temp_file = NamedTemporaryFile()
    temp_file.close()

    temp_path = Path(temp_file.name)
    try:
        yield temp_path
    finally:
        temp_path.unlink(missing_ok=True)


@contextmanager
def source_to_cil_policy(policy_path: Path):
    with _compiled_policy_path() as cil_path:
        run_cmd(
            [
                str(checkpolicy_path),
                '-C',
                '-M',
                '-L',
                '-c',
                '30',
                str(policy_path),
                '-o',
                str(cil_path),
            ]
        )

        yield cil_path


@contextmanager
def cil_to_binary_policy(policy_path: Path):
    with _compiled_policy_path() as binary_path:
        run_cmd(
            [
                str(secilc_path),
                # '-v', # no verbose
                '-m',
                '-M',
                'true',
                '-G',
                '-c',
                '30',
                # ignore neverallows
                '-N',
                str(policy_path),
                '-o',
                str(binary_path),
                '-f',
                '/dev/null',
            ]
        )

        yield binary_path


@contextmanager
def binary_to_cil_policy(policy_path: Path):
    with _compiled_policy_path() as cil_path:
        run_cmd(
            [
                str(checkpolicy_path),
                '-C',
                '-M',
                '-b',
                str(policy_path),
                '-o',
                str(cil_path),
            ]
        )

        yield cil_path

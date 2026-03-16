# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from functools import partial
from itertools import chain
from pathlib import Path
from typing import Dict, List, Optional, Set

from sepolicy.cil_rule import CilRule
from sepolicy.conditional_type import ConditionalType
from sepolicy.match import merge_ioctl_rules
from sepolicy.rule import Rule


def decompile_one_cil(
    cil_path: Path,
    conditional_types_map: Dict[str, ConditionalType],
    missing_generated_types: Set[str],
    version: Optional[str],
    name: str,
):
    cil_data = cil_path.read_text()
    cil_lines = cil_data.splitlines()

    genfs_rules: List[Rule] = []

    # Convert lines to rules
    fn = partial(
        CilRule.from_line,
        conditional_types_map=conditional_types_map,
        missing_generated_types=missing_generated_types,
        genfs_rules=genfs_rules,
        version=version,
    )
    rules = list(chain.from_iterable(map(fn, cil_lines)))

    # ioctl rules are split at comments / newlines by the compiler
    # merge adjacent ioctl rules of the same type back
    # TODO: this won't work if the rules end up next to eachother but
    # they weren't next to eachother initially, but the chances for that
    # are very low
    rules = merge_ioctl_rules(rules, name)

    return rules, genfs_rules

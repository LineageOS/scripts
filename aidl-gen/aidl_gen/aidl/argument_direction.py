#
# Copyright (C) 2023 The LineageOS Project
#
# SPDX-License-Identifier: Apache-2.0
#

from enum import Enum
from typing import Optional

class ArgumentDirection(Enum):
    IN = "in"
    OUT = "out"
    INOUT = "inout"

    @classmethod
    def from_value(cls, value: str) -> Optional["ArgumentDirection"]:
        try:
            return cls(value)
        except ValueError:
            return None

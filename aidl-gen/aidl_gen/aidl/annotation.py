#
# Copyright (C) 2023 The LineageOS Project
#
# SPDX-License-Identifier: Apache-2.0
#

from enum import Enum
from typing import Optional

class Annotation(Enum):
    NULLABLE = "@nullable"

    @classmethod
    def from_value(cls, value: str) -> Optional["Annotation"]:
        try:
            return cls(value)
        except ValueError:
            return None

#
# Copyright (C) 2023 The LineageOS Project
#
# SPDX-License-Identifier: Apache-2.0
#

from enum import Enum
from typing import Optional

class CollectionType(Enum):
    ARRAY = "T[]"
    LIST = "List<T>"
    FIXED_SIZE_ARRAY = "T[N]"

    @classmethod
    def from_value(cls, value: str) -> Optional["CollectionType"]:
        try:
            return cls(value)
        except ValueError:
            return None

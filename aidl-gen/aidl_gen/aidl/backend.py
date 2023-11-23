#
# Copyright (C) 2023 The LineageOS Project
#
# SPDX-License-Identifier: Apache-2.0
#

from enum import Enum
from typing import Optional

class Backend(Enum):
    JAVA = "java"
    CPP = "cpp"
    NDK = "ndk"
    RUST = "rust"

    def __str__(self):
        return self.value

    @classmethod
    def from_value(cls, value: str) -> Optional["Backend"]:
        try:
            return cls(value)
        except ValueError:
            return None

#
# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0
#

from enum import Enum
from typing import Optional
from warnings import warn

from aidl_gen.aidl.package import Package

class Backend(Enum):
    JAVA = "java"
    CPP = "cpp"
    NDK = "ndk"
    RUST = "rust"

    def __str__(self):
        return self.value

    def get_aosp_library_name(self, package: Package, version: int) -> str:
        if version == Package.VERSION_CURRENT:
            warn("Usage of current version is discouraged, please use a frozen version instead")

            return f"{package.name}-{self.value}"

        return f"{package.name}-V{version}-{self.value}"

    @classmethod
    def from_value(cls, value: str) -> Optional["Backend"]:
        try:
            return cls(value)
        except ValueError:
            return None

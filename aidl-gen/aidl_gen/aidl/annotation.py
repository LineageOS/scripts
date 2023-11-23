#
# Copyright (C) 2023 The LineageOS Project
#
# SPDX-License-Identifier: Apache-2.0
#

from enum import Enum
from typing import Optional

class Annotation(Enum):
    NULLABLE = "@nullable"
    UTF8_IN_CPP = "@utf8InCpp"
    VINTF_STABILITY = "@VintfStability"
    UNSUPPORTED_APP_USAGE = "@UnsupportedAppUsage"
    HIDE = "@Hide"
    BACKING = "@Backing"
    NDK_ONLY_STABLE_PARCELABLE = "@NdkOnlyStableParcelable"
    JAVA_ONLY_STABLE_PARCELABLE = "@JavaOnlyStableParcelable"
    JAVA_DERIVE = "@JavaDerive"
    JAVA_PASSTHROUGH = "@JavaPassthrough"
    FIXED_SIZE = "@FixedSize"
    DESCRIPTOR = "@Descriptor"

    @classmethod
    def from_value(cls, value: str) -> Optional["Annotation"]:
        try:
            return cls(value)
        except ValueError:
            return None

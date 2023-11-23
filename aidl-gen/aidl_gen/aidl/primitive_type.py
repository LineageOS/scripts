#
# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0
#

from enum import Enum
from typing import Optional

class PrimitiveType(Enum):
    VOID = "void"
    BOOLEAN = "boolean"
    BYTE = "byte"
    CHAR = "char"
    INT = "int"
    LONG = "long"
    FLOAT = "float"
    DOUBLE = "double"
    STRING = "String"
    PARCELABLE = "android.os.Parcelable"
    IBINDER = "IBinder"
    FILE_DESCRIPTOR = "FileDescriptor"
    PARCEL_FILE_DESCRIPTOR = "ParcelFileDescriptor"

    @classmethod
    def from_value(cls, value: str) -> Optional["PrimitiveType"]:
        try:
            return cls(value)
        except ValueError:
            return None

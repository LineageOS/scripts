#
# Copyright (C) 2023 The LineageOS Project
#
# SPDX-License-Identifier: Apache-2.0
#

from enum import Enum

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

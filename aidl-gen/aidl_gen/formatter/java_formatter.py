#
# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0
#

from pathlib import Path
from typing import Dict, Optional

from aidl_gen.aidl.interface import Interface
from aidl_gen.aidl.package import Package
from aidl_gen.aidl.primitive_type import PrimitiveType
from aidl_gen.formatter.backend import Backend
from aidl_gen.formatter.formatter import Formatter
from aidl_gen.parser import Parser

# Source: https://source.android.com/devices/architecture/aidl/aidl-backends#types
AIDL_TO_JAVA_TYPE: Dict[PrimitiveType, Optional[str]] = {
    PrimitiveType.VOID: "void",
    PrimitiveType.BOOLEAN: "bool",
    PrimitiveType.BYTE: "byte",
    PrimitiveType.CHAR: "char",
    PrimitiveType.INT: "int",
    PrimitiveType.LONG: "long",
    PrimitiveType.FLOAT: "float",
    PrimitiveType.DOUBLE: "double",
    PrimitiveType.STRING: "String",
    PrimitiveType.PARCELABLE: "android.os.Parcelable",
    PrimitiveType.IBINDER: "android.os.IBinder",
    PrimitiveType.FILE_DESCRIPTOR: "android.os.FileDescriptor",
    PrimitiveType.PARCEL_FILE_DESCRIPTOR: "android.os.ParcelFileDescriptor",
}

class JavaFormatter(Formatter):
    BACKEND = Backend.JAVA

    @classmethod
    def _dump_to_folder(
        cls,
        package: Package,
        version: int,
        interface: Interface,
        parser: Parser,
        folder: Path,
        template_kwargs: Dict[str, str],
    ):
        return super()._dump_to_folder(package, version, interface, parser, folder, template_kwargs)

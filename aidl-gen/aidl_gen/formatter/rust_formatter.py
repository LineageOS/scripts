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
AIDL_TO_RUST_TYPE: Dict[PrimitiveType, Optional[str]] = {
    PrimitiveType.VOID: "void",
    PrimitiveType.BOOLEAN: "bool",
    PrimitiveType.BYTE: "i8",
    PrimitiveType.CHAR: "u16",
    PrimitiveType.INT: "i32",
    PrimitiveType.LONG: "i64",
    PrimitiveType.FLOAT: "float",
    PrimitiveType.DOUBLE: "double",
    PrimitiveType.STRING: "String",
    PrimitiveType.PARCELABLE: None,
    PrimitiveType.IBINDER: "::binder::SpIBinder",
    PrimitiveType.FILE_DESCRIPTOR: "::binder::parcel::ParcelFileDescriptor",
    PrimitiveType.PARCEL_FILE_DESCRIPTOR: "::binder::parcel::ParcelFileDescriptor",
}

class RustFormatter(Formatter):
    BACKEND = Backend.RUST

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

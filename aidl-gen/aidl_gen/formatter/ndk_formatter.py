#
# Copyright (C) 2023 The LineageOS Project
#
# SPDX-License-Identifier: Apache-2.0
#

from pathlib import Path
from typing import Dict, Optional, Union

from aidl_gen.aidl.annotation import Annotation
from aidl_gen.formatter.backend import Backend
from aidl_gen.aidl.collection_type import CollectionType
from aidl_gen.aidl.data_type import DataType
from aidl_gen.aidl.interface import Interface
from aidl_gen.aidl.method import Method
from aidl_gen.aidl.method_argument import MethodArgument
from aidl_gen.aidl.package import Package
from aidl_gen.aidl.parcelable import Parcelable
from aidl_gen.aidl.primitive_type import PrimitiveType
from aidl_gen.formatter.formatter import Formatter
from aidl_gen.parser import Parser

# Source: https://source.android.com/devices/architecture/aidl/aidl-backends#types
AIDL_TO_NDK_TYPE: Dict[PrimitiveType, Union[str, None]] = {
    PrimitiveType.VOID: "void",
    PrimitiveType.BOOLEAN: "bool",
    PrimitiveType.BYTE: "int8_t",
    PrimitiveType.CHAR: "char16_t",
    PrimitiveType.INT: "int32_t",
    PrimitiveType.LONG: "int64_t",
    PrimitiveType.FLOAT: "float",
    PrimitiveType.FLOAT: "double",
    PrimitiveType.STRING: "::std::string",
    PrimitiveType.PARCELABLE: None,
    PrimitiveType.IBINDER: "::ndk::SpAIBinder",
    PrimitiveType.FILE_DESCRIPTOR: None,
    PrimitiveType.PARCEL_FILE_DESCRIPTOR: "::ndk::ScopedFileDescriptor",
}

ANDROID_BP_TEMPLATE = \
"""
cc_binary {{
    name: "{aidl_name}-service",
    relative_install_path: "hw",
    init_rc: ["{aidl_name}-service.rc"],
    vintf_fragments: ["{aidl_name}-service.xml"],
    srcs: [
        "{class_name}.cpp",
        "service.cpp",
    ],
    shared_libs: [
        "libbase",
        "libbinder_ndk",
        "{interface_aosp_library_name}",
    ],
    vendor: true,
}}
"""

MAIN_CPP_TEMPLATE = \
"""
#include "{class_name}.h"

namespace aidl {{
{aidl_namespace_open}

{methods_definitions}

{aidl_namespace_close}
}} // namespace aidl
"""

MAIN_H_TEMPLATE = \
"""
#pragma once

#include <aidl/{aidl_path}/Bn{class_name}.h>

namespace aidl {{
{aidl_namespace_open}

class {class_name} : public Bn{class_name} {{
  public:
{methods_declarations}
}};

{aidl_namespace_close}
}} // namespace aidl
"""

SERVICE_CPP_TEMPLATE = \
"""
#include "{class_name}.h"

#include <android/binder_manager.h>
#include <android/binder_process.h>
#include <android-base/logging.h>

using aidl::{aidl_namespace}::{class_name};

int main() {{
    ABinderProcess_setThreadPoolMaxThreadCount(0);
    std::shared_ptr<{class_name}> {class_name_lower} = ndk::SharedRefBase::make<{class_name}>();

    const std::string instance = std::string() + {class_name}::descriptor + "/default";
    binder_status_t status = AServiceManager_addService({class_name_lower}->asBinder().get(), instance.c_str());
    CHECK(status == STATUS_OK);

    ABinderProcess_joinThreadPool();
    return EXIT_FAILURE;  // should not reach
}}
"""

class NDKFormatter(Formatter):
    BACKEND = Backend.NDK

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
        assert folder.is_dir(), f"{folder} is not a directory"

        aidl_name = template_kwargs["aidl_name"]
        class_name = template_kwargs["class_name"]
        aidl_namespace = aidl_name.replace('.', "::")
        aidl_path = aidl_name.replace('.', "/")
        aidl_namespace_open = "\n".join(
            [f"namespace {namespace} {{"
            for namespace in aidl_name.split('.')
        ])
        aidl_namespace_close = "\n".join([
            f"}} // namespace {namespace}"
            for namespace in aidl_name.split('.')[::-1]
        ])

        methods_declarations = "\n".join([
            f"    {cls.format_method(method, parser)};"
            for method in interface.methods
        ])

        methods_definitions = "\n\n".join([
            "\n".join([
                f"{cls.format_method(method, parser, class_name)} {{",
                "    return ::ndk::ScopedAStatus::fromExceptionCode(EX_UNSUPPORTED_OPERATION);",
                "}",
            ])
            for method in interface.methods
        ])

        template_kwargs.update(
            {
                "aidl_namespace": aidl_namespace,
                "aidl_path": aidl_path,
                "aidl_namespace_open": aidl_namespace_open,
                "aidl_namespace_close": aidl_namespace_close,
                "methods_declarations": methods_declarations,
                "methods_definitions": methods_definitions,
            }
        )

        (folder / "Android.bp").write_text(cls.format_template_with_license(
            ANDROID_BP_TEMPLATE, *cls.BLUEPRINT_COMMENT, **template_kwargs
        ))
        (folder / f"{class_name}.cpp").write_text(cls.format_template_with_license(
            MAIN_CPP_TEMPLATE, *cls.CPP_COMMENT, **template_kwargs
        ))
        (folder / f"{class_name}.h").write_text(cls.format_template_with_license(
            MAIN_H_TEMPLATE, *cls.CPP_COMMENT, **template_kwargs
        ))
        (folder / "service.cpp").write_text(cls.format_template_with_license(
            SERVICE_CPP_TEMPLATE, *cls.CPP_COMMENT, **template_kwargs
        ))

    @classmethod
    def format_method(
        cls,
        method: Method,
        parser: Parser,
        class_name: Optional[str] = None,
    ):
        """Formats a method to a string. If class_name is None, it will return a declaration, otherwise it will return a definition."""
        method_return_type = cls.format_data_type(method.return_type, parser)

        arg_name_comment_start = "/*" if class_name else ""
        arg_name_comment_end = "*/" if class_name else ""

        method_arguments = [
            cls.format_method_argument(arg, parser, class_name is not None)
            for arg in method.arguments
        ]
        if method.return_type.data_type != PrimitiveType.VOID:
            method_arguments.append(f"{method_return_type}* {arg_name_comment_start}_aidl_return{arg_name_comment_end}")

        if class_name is None:
            return f"::ndk::ScopedAStatus {method.name}({', '.join(method_arguments)})"
        else:
            return f"::ndk::ScopedAStatus {class_name}::{method.name}({', '.join(method_arguments)})"

    @classmethod
    def format_method_argument(
        cls,
        method_argument: MethodArgument,
        parser: Parser,
        comment_argument_name: bool = False,
    ) -> str:
        arg_name_comment_start = "/*" if comment_argument_name else ""
        arg_name_comment_end = "*/" if comment_argument_name else ""

        data_type = cls.format_data_type(method_argument.data_type, parser)

        nullable = any(
            annotation.annotation_type == Annotation.Type.NULLABLE
            for annotation in method_argument.annotations
        )
        if nullable:
            data_type = f"std::optional<{data_type}>"
        
        nested_data_type = method_argument.data_type
        while isinstance(nested_data_type, DataType):
            nested_data_type = nested_data_type.data_type
        
        if isinstance(nested_data_type, str):
            nested_aidl_entity = parser.import_aidl(nested_data_type)

            if isinstance(nested_aidl_entity, Parcelable):
                # Parcelables must be const references
                data_type = f"const {data_type}&"

        return f"{data_type} {arg_name_comment_start}{method_argument.name}{arg_name_comment_end}"

    @classmethod
    def format_data_type(
        cls,
        data_type: DataType,
        parser: Parser,
    ) -> str:
        result = ""

        if isinstance(data_type.data_type, DataType):
            result = cls.format_data_type(data_type.data_type, parser)
        elif isinstance(data_type.data_type, PrimitiveType):
            result = AIDL_TO_NDK_TYPE[data_type.data_type]
            assert result is not None, f"Primitive type {data_type.data_type} not supported by the backend"
        elif isinstance(data_type.data_type, str):
            result = f"::aidl::{data_type.data_type.replace('.', '::')}"

            aidl_entity = parser.import_aidl(data_type.data_type)
            assert aidl_entity is not None, f"Unknown AIDL entity {data_type.data_type}"

            if isinstance(aidl_entity, Interface):
                # Interfaces must use shared_ptr
                result = f"::std::shared_ptr<{result}>"
        else:
            raise NotImplementedError(f"Unknown data type {data_type.data_type}")

        if data_type.collection_type is CollectionType.ARRAY:
            result = f"::std::vector<{result}>"
        elif data_type.collection_type is CollectionType.LIST:
            result = f"::std::vector<{result}>"
        elif data_type.collection_type is CollectionType.FIXED_SIZE_ARRAY:
            result = f"::std::array<{result}, {data_type.array_size}>"

        return result

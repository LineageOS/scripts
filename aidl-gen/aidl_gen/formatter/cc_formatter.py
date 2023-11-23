#
# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0
#

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from aidl_gen.aidl.annotation import Annotation
from aidl_gen.aidl.collection_type import CollectionType
from aidl_gen.aidl.data_type import DataType
from aidl_gen.aidl.enum import Enum
from aidl_gen.aidl.interface import Interface
from aidl_gen.aidl.method import Method
from aidl_gen.aidl.method_argument import MethodArgument
from aidl_gen.aidl.package import Package
from aidl_gen.aidl.parcelable import Parcelable
from aidl_gen.aidl.primitive_type import PrimitiveType
from aidl_gen.formatter.formatter import Formatter
from aidl_gen.parser import Parser

ANDROID_BP_TEMPLATE = \
"""
cc_binary {{
    name: "{target_name}",
    relative_install_path: "hw",
    vendor: true,
    init_rc: ["{init_rc_name}"],
    vintf_fragments: ["{vintf_fragment_name}"],
    srcs: [
        "{class_name}.cpp",
        "service.cpp",
    ],
    shared_libs: [
{shared_libs}
        "{interface_aosp_library_name}",
    ],
}}
"""

MAIN_CPP_TEMPLATE = \
"""
#include "{class_name}.h"

{impl_namespace_open}

{methods_definitions}

{impl_namespace_close}
"""

MAIN_H_TEMPLATE = \
"""
#pragma once

#include {interface_bn_include}

{impl_namespace_open}

class {class_name} : public Bn{class_name} {{
  public:
{methods_declarations}
}};

{impl_namespace_close}
"""

class CCFormatter(Formatter):
    SERVICE_CPP_TEMPLATE: str
    SHARED_LIBS: List[str]
    STATUS_TYPE: str
    SHARED_POINTER_TYPE: str
    TODO_RETURN_TYPE: str
    AIDL_TO_CC_TYPE: Dict[PrimitiveType, Optional[str]]

    @classmethod
    def _dump_to_folder(
        cls,
        package: Package,
        version: int,
        interface: Interface,
        parser: Parser,
        folder: Path,
        template_kwargs: Dict[str, Any],
    ):
        assert folder.is_dir(), f"{folder} is not a directory"

        aidl_name = template_kwargs["aidl_name"]
        impl_class_name = template_kwargs["class_name"]

        interface_bn_include = cls._get_interface_bn_include(aidl_name, impl_class_name)

        impl_namespace = cls._get_implementation_namespace(aidl_name)
        impl_namespace_open = "\n".join(
            [f"namespace {namespace} {{"
            for namespace in impl_namespace
        ])
        impl_namespace_close = "\n".join([
            f"}} // namespace {namespace}"
            for namespace in impl_namespace[::-1]
        ])

        methods_declarations = "\n".join([
            f"    {cls._format_method(method, parser)} override;"
            for method in interface.methods
        ])

        methods_definitions = "\n\n".join([
            "\n".join([
                f"{cls._format_method(method, parser, impl_class_name)} {{",
                "    return {TODO_RETURN_TYPE};".format(TODO_RETURN_TYPE = cls.TODO_RETURN_TYPE),
                "}",
            ])
            for method in interface.methods
        ])

        shared_libs = "\n".join([
            f'        "{shared_lib}",'
            for shared_lib in cls.SHARED_LIBS
        ])

        template_kwargs.update(
            {
                "impl_namespace": "::".join(impl_namespace),
                "impl_namespace_open": impl_namespace_open,
                "impl_namespace_close": impl_namespace_close,
                "interface_bn_include": interface_bn_include,
                "methods_declarations": methods_declarations,
                "methods_definitions": methods_definitions,
                "shared_libs": shared_libs,
            }
        )

        (folder / "Android.bp").write_text(cls.format_template_with_license(
            ANDROID_BP_TEMPLATE, *cls.BLUEPRINT_COMMENT, **template_kwargs
        ))
        (folder / f"{impl_class_name}.cpp").write_text(cls.format_template_with_license(
            MAIN_CPP_TEMPLATE, *cls.CPP_COMMENT, **template_kwargs
        ))
        (folder / f"{impl_class_name}.h").write_text(cls.format_template_with_license(
            MAIN_H_TEMPLATE, *cls.CPP_COMMENT, **template_kwargs
        ))
        (folder / "service.cpp").write_text(cls.format_template_with_license(
            cls.SERVICE_CPP_TEMPLATE, *cls.CPP_COMMENT, **template_kwargs
        ))

    @classmethod
    def _get_interface_bn_include(cls, aidl_name: str, class_name: str) -> str:
        raise NotImplementedError()

    @classmethod
    def _get_implementation_namespace(cls, aidl_name: str) -> List[str]:
        raise NotImplementedError()

    @classmethod
    def _format_aidl_data_type(cls, data_type_name: str) -> str:
        raise NotImplementedError()

    @classmethod
    def _format_method(
        cls,
        method: Method,
        parser: Parser,
        class_name: Optional[str] = None,
    ):
        """
        Formats a method to a string. If class_name is None, it will return a declaration,
        otherwise it will return a definition.
        """
        method_return_type = cls._format_data_type(method.return_type, parser)

        arg_name_comment_start = "/*" if class_name else ""
        arg_name_comment_end = "*/" if class_name else ""

        method_arguments = [
            cls._format_method_argument(arg, parser, class_name is not None)
            for arg in method.arguments
        ]
        if method.return_type.data_type != PrimitiveType.VOID:
            method_arguments.append(
                f"{method_return_type}* {arg_name_comment_start}_aidl_return{arg_name_comment_end}"
            )

        method_arguments_str = ", ".join(method_arguments)

        if class_name is None:
            return f"{cls.STATUS_TYPE} {method.name}({method_arguments_str})"
        else:
            return f"{cls.STATUS_TYPE} {class_name}::{method.name}({method_arguments_str})"

    @classmethod
    def _format_method_argument(
        cls,
        method_argument: MethodArgument,
        parser: Parser,
        comment_argument_name: bool = False,
    ) -> str:
        arg_name_comment_start = "/*" if comment_argument_name else ""
        arg_name_comment_end = "*/" if comment_argument_name else ""

        data_type = cls._format_data_type(method_argument.data_type, parser)

        nested_data_type = method_argument.data_type
        while isinstance(nested_data_type, DataType):
            nested_data_type = nested_data_type.data_type

        nested_aidl_entity: Optional[Union[Enum, Interface, Parcelable]] = None
        if isinstance(nested_data_type, str):
            nested_aidl_entity = parser.import_aidl(nested_data_type)

        nullable = any(
            annotation.annotation_type == Annotation.Type.NULLABLE
            for annotation in method_argument.annotations
        )
        if nullable and not isinstance(nested_aidl_entity, Interface):
            data_type = f"::std::optional<{data_type}>"

        if isinstance(nested_aidl_entity, (Interface, Parcelable)):
            # Interfaces and parcelables must be const references
            data_type = f"const {data_type}&"

        return f"{data_type} {arg_name_comment_start}{method_argument.name}{arg_name_comment_end}"

    @classmethod
    def _format_data_type(
        cls,
        data_type: DataType,
        parser: Parser,
    ) -> str:
        result = ""

        if isinstance(data_type.data_type, DataType):
            result = cls._format_data_type(data_type.data_type, parser)
        elif isinstance(data_type.data_type, PrimitiveType):
            result = cls.AIDL_TO_CC_TYPE[data_type.data_type]
            assert result is not None, \
                f"Primitive type {data_type.data_type} not supported by the backend"
        elif isinstance(data_type.data_type, str):
            result = cls._format_aidl_data_type(data_type.data_type)

            aidl_entity = parser.import_aidl(data_type.data_type)

            if isinstance(aidl_entity, Interface):
                # Interfaces must use a shared pointer
                result = f"{cls.SHARED_POINTER_TYPE}<{result}>"
        else:
            raise NotImplementedError(f"Unknown data type {data_type.data_type}")

        if data_type.collection_type is CollectionType.ARRAY:
            result = f"::std::vector<{result}>"
        elif data_type.collection_type is CollectionType.LIST:
            result = f"::std::vector<{result}>"
        elif data_type.collection_type is CollectionType.FIXED_SIZE_ARRAY:
            result = f"::std::array<{result}, {data_type.array_size}>"

        return result

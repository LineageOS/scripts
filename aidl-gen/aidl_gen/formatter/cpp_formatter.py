#
# Copyright (C) 2023 The LineageOS Project
#
# SPDX-License-Identifier: Apache-2.0
#

# Source: https://source.android.com/devices/architecture/aidl/aidl-backends#types
from pathlib import Path
from typing import Dict
from aidl_gen.aidl.backend import Backend
from aidl_gen.aidl.collection_type import CollectionType
from aidl_gen.aidl.data_type import DataType
from aidl_gen.aidl.interface import Interface
from aidl_gen.aidl.package import Package
from aidl_gen.aidl.primitive_type import PrimitiveType
from aidl_gen.formatter.formatter import Formatter

AIDL_TO_CPP_TYPE = {
    PrimitiveType.VOID: "void",
    PrimitiveType.BOOLEAN: "bool",
    PrimitiveType.BYTE: "int8_t",
    PrimitiveType.CHAR: "char16_t",
    PrimitiveType.INT: "int32_t",
    PrimitiveType.LONG: "int64_t",
    PrimitiveType.FLOAT: "float",
    PrimitiveType.FLOAT: "double",
    PrimitiveType.STRING: "::android::String16",
    PrimitiveType.PARCELABLE: "::android::Parcelable",
    PrimitiveType.IBINDER: "::android::IBinder",
    PrimitiveType.FILE_DESCRIPTOR: "::android::base::unique_fd",
    PrimitiveType.PARCEL_FILE_DESCRIPTOR: "::android::os::ParcelFileDescriptor",
    # "interface type (T)": "::android::sp<T>", # Dealt with in AIDLMethodArgument
    # "parcelable type (T)": "T", # No intervention required
    # "union type (T)": "T", # No intervention required
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

{using_namespaces}

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

using ::aidl::{aidl_namespace}::{class_name};

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

class CPPFormatter(Formatter):
    BACKEND = Backend.CPP

    @classmethod
    def _dump_to_folder(
        cls,
        package: Package,
        interface: Interface,
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

        methods_definitions = "\n\n".join([
            f"{cls.format_data_type(method.return_type)} {class_name}::{method.name}({', '.join([f'{cls.format_data_type(arg.data_type)} {arg.name}' for arg in method.arguments])}) {{"
            for method in interface.methods
        ]) + "\n}"

        template_kwargs.update(
            {
                "aidl_namespace": aidl_namespace,
                "aidl_path": aidl_path,
                "aidl_namespace_open": aidl_namespace_open,
                "aidl_namespace_close": aidl_namespace_close,
                "methods_definitions": methods_definitions,
            }
        )

        (folder / "Android.bp").write_text(cls.format_template_with_license(
            ANDROID_BP_TEMPLATE, "//", "// ", "//", **template_kwargs
        ))
        (folder / f"{class_name}.cpp").write_text(cls.format_template_with_license(
            MAIN_CPP_TEMPLATE, "/*", " * ", " */", **template_kwargs
        ))
        """
        (folder / f"{class_name}.h").write_text(cls.format_template_with_license(
            MAIN_H_TEMPLATE, "/*", " * ", " */", **template_kwargs
        ))
        """
        (folder / "service.cpp").write_text(cls.format_template_with_license(
            SERVICE_CPP_TEMPLATE, "/*", " * ", " */", **template_kwargs
        ))

    @classmethod
    def format_data_type(cls, data_type: DataType) -> str:
        result = ""

        if isinstance(data_type.data_type, DataType):
            result = cls.format_data_type(data_type.data_type)
        elif isinstance(data_type.data_type, PrimitiveType):
            result = AIDL_TO_CPP_TYPE[data_type.data_type]
        elif isinstance(data_type.data_type, str):
            result = data_type.data_type
        else:
            raise NotImplementedError(f"Unknown data type {data_type.data_type}")

        if data_type.collection_type is CollectionType.ARRAY:
            result = f"std::vector<{result}>"
        elif data_type.collection_type is CollectionType.LIST:
            result = f"std::vector<{result}>"
        elif data_type.collection_type is CollectionType.FIXED_SIZE_ARRAY:
            result = f"std::array<{result}, {data_type.array_size}>"

        return result

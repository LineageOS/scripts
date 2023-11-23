#
# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0
#

from typing import Dict, List, Optional

from aidl_gen.aidl.primitive_type import PrimitiveType
from aidl_gen.formatter.backend import Backend
from aidl_gen.formatter.cc_formatter import CCFormatter

# Source: https://source.android.com/devices/architecture/aidl/aidl-backends#types
AIDL_TO_NDK_TYPE: Dict[PrimitiveType, Optional[str]] = {
    PrimitiveType.VOID: "void",
    PrimitiveType.BOOLEAN: "bool",
    PrimitiveType.BYTE: "int8_t",
    PrimitiveType.CHAR: "char16_t",
    PrimitiveType.INT: "int32_t",
    PrimitiveType.LONG: "int64_t",
    PrimitiveType.FLOAT: "float",
    PrimitiveType.DOUBLE: "double",
    PrimitiveType.STRING: "::std::string",
    PrimitiveType.PARCELABLE: None,
    PrimitiveType.IBINDER: "::ndk::SpAIBinder",
    PrimitiveType.FILE_DESCRIPTOR: None,
    PrimitiveType.PARCEL_FILE_DESCRIPTOR: "::ndk::ScopedFileDescriptor",
}

SERVICE_CPP_TEMPLATE = \
"""
#include "{class_name}.h"

#include <android/binder_manager.h>
#include <android/binder_process.h>
#include <android-base/logging.h>

using {impl_namespace}::{class_name};

int main() {{
    ABinderProcess_setThreadPoolMaxThreadCount(0);
    std::shared_ptr<{class_name}> hal = ::ndk::SharedRefBase::make<{class_name}>();

    const std::string instance = std::string({class_name}::descriptor) + "/default";
    binder_status_t status = AServiceManager_addService(hal->asBinder().get(), instance.c_str());
    CHECK_EQ(status, STATUS_OK);

    ABinderProcess_joinThreadPool();
    return EXIT_FAILURE;  // should not reach
}}
"""

class NDKFormatter(CCFormatter):
    BACKEND = Backend.NDK

    SERVICE_CPP_TEMPLATE = SERVICE_CPP_TEMPLATE
    SHARED_LIBS = [
        "libbase",
        "libbinder_ndk",
    ]
    STATUS_TYPE = "::ndk::ScopedAStatus"
    SHARED_POINTER_TYPE = "::std::shared_ptr"
    TODO_RETURN_TYPE = "::ndk::ScopedAStatus::fromExceptionCode(EX_UNSUPPORTED_OPERATION)"
    AIDL_TO_CC_TYPE = AIDL_TO_NDK_TYPE

    @classmethod
    def _get_interface_bn_include(cls, aidl_name: str, class_name: str) -> str:
        return f"<aidl/{aidl_name.replace('.', '/')}/Bn{class_name}.h>"

    @classmethod
    def _get_implementation_namespace(cls, aidl_name: str) -> List[str]:
        return f"aidl.{aidl_name}".split('.')

    @classmethod
    def _format_aidl_data_type(cls, data_type_name: str) -> str:
        return f"::aidl::{data_type_name.replace('.', '::')}"

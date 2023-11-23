#
# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0
#

from typing import Dict, List, Optional

from aidl_gen.aidl.primitive_type import PrimitiveType
from aidl_gen.formatter.backend import Backend
from aidl_gen.formatter.cc_formatter import CCFormatter

# Source: https://source.android.com/devices/architecture/aidl/aidl-backends#types
AIDL_TO_CPP_TYPE: Dict[PrimitiveType, Optional[str]] = {
    PrimitiveType.VOID: "void",
    PrimitiveType.BOOLEAN: "bool",
    PrimitiveType.BYTE: "int8_t",
    PrimitiveType.CHAR: "char16_t",
    PrimitiveType.INT: "int32_t",
    PrimitiveType.LONG: "int64_t",
    PrimitiveType.FLOAT: "float",
    PrimitiveType.DOUBLE: "double",
    PrimitiveType.STRING: "::android::String16",
    PrimitiveType.PARCELABLE: "::android::Parcelable",
    PrimitiveType.IBINDER: "::android::IBinder",
    PrimitiveType.FILE_DESCRIPTOR: "::android::base::unique_fd",
    PrimitiveType.PARCEL_FILE_DESCRIPTOR: "::android::os::ParcelFileDescriptor",
}

SERVICE_CPP_TEMPLATE = \
"""
#include "{class_name}.h"

#include <binder/IPCThreadState.h>
#include <binder/IServiceManager.h>
#include <binder/ProcessState.h>
#include <android-base/logging.h>

using {impl_namespace}::{class_name};

int main() {{
    ::android::ProcessState::self()->setThreadPoolMaxThreadCount(0);
    ::android::sp<{class_name}> service = ::android::sp<{class_name}>::make();

    const ::android::String16 name = {class_name}::descriptor + ::android::String16("/default");
    ::android::status_t status = ::android::defaultServiceManager()->addService(name, service);
    CHECK_EQ(status, ::android::OK);

    ::android::IPCThreadState::self()->joinThreadPool();
    return EXIT_FAILURE;  // should not reach
}}
"""

class CPPFormatter(CCFormatter):
    BACKEND = Backend.CPP

    SERVICE_CPP_TEMPLATE = SERVICE_CPP_TEMPLATE
    SHARED_LIBS = [
        "libbase",
        "libbinder",
        "libutils",
    ]
    STATUS_TYPE = "::android::binder::Status"
    SHARED_POINTER_TYPE = "::android::sp"
    TODO_RETURN_TYPE = "::android::binder::Status::fromExceptionCode(::android::binder::Status::EX_UNSUPPORTED_OPERATION)"
    AIDL_TO_CC_TYPE = AIDL_TO_CPP_TYPE

    @classmethod
    def _get_interface_bn_include(cls, aidl_name: str, class_name: str) -> str:
        return f"<{aidl_name.replace('.', '/')}/Bn{class_name}.h>"

    @classmethod
    def _get_implementation_namespace(cls, aidl_name: str) -> List[str]:
        return aidl_name.split('.')

    @classmethod
    def _format_aidl_data_type(cls, data_type_name: str) -> str:
        return data_type_name.replace('.', '::')

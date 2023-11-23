#
# Copyright (C) 2023 The LineageOS Project
#
# SPDX-License-Identifier: Apache-2.0
#

# Source: https://source.android.com/devices/architecture/aidl/aidl-backends#types
AIDL_TO_NDK_TYPE = {
    "boolean": "bool",
    "byte": "int8_t",
    "char": "char16_t",
    "int": "int32_t",
    "long": "int64_t",
    "float": "float",
    "double": "double",
    "String": "::std::string",
    "android.os.Parcelable": None,
    "IBinder": "::ndk::SpAIBinder",
    "FileDescriptor": None,
    "ParcelFileDescriptor": "::ndk::ScopedFileDescriptor",
    # "interface type (T)": "::std::shared_ptr<T>", # Dealt with in AIDLMethodArgument
    # "parcelable type (T)": "T", # No intervention required
    # "union type (T)": "T", # No intervention required
}

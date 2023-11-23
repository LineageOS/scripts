#
# Copyright (C) 2023 The LineageOS Project
#
# SPDX-License-Identifier: Apache-2.0
#

# Source: https://source.android.com/devices/architecture/aidl/aidl-backends#types
AIDL_TO_CPP_TYPE = {
    "boolean": "bool",
    "byte": "int8_t",
    "char": "char16_t",
    "int": "int32_t",
    "long": "int64_t",
    "float": "float",
    "double": "double",
    "String": "::android::String16",
    "android.os.Parcelable": "::android::Parcelable",
    "IBinder": "::android::IBinder",
    # "T[]": "std::vector<T>", # Dealt with in AIDLMethodArgument
    # "byte[]": "std::vector<uint8_t>", # "byte" match will handle this
    # "List<T>": "std::vector<T>", # Dealt with in AIDLMethodArgument
    "FileDescriptor": "::android::base::unique_fd",
    "ParcelFileDescriptor": "::android::os::ParcelFileDescriptor",
    # "interface type (T)": "::android::sp<T>", # Dealt with in AIDLMethodArgument
    # "parcelable type (T)": "T", # No intervention required
    # "union type (T)": "T", # No intervention required
}

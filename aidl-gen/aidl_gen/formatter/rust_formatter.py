#
# Copyright (C) 2023 The LineageOS Project
#
# SPDX-License-Identifier: Apache-2.0
#

# Source: https://source.android.com/devices/architecture/aidl/aidl-backends#types
AIDL_TO_RUST_TYPE = {
    "boolean": "bool",
    "byte": "i8",
    "char": "u16",
    "int": "i32",
    "long": "i64",
    "float": "float",
    "double": "double",
    "String": "String",
    "android.os.Parcelable": None,
    "IBinder": "::binder::SpIBinder",
    "FileDescriptor": "::binder::parcel::ParcelFileDescriptor",
    "ParcelFileDescriptor": "::binder::parcel::ParcelFileDescriptor",
    # "interface type (T)": "::android::sp<T>", # Dealt with in AIDLMethodArgument
    # "parcelable type (T)": "T", # No intervention required
    # "union type (T)": "T", # No intervention required
}

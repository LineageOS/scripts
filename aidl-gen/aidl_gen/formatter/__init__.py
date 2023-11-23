#
# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0
#
"""AIDL backend formatters."""

from typing import Type

from aidl_gen.formatter.backend import Backend
from aidl_gen.formatter.cpp_formatter import CPPFormatter
from aidl_gen.formatter.java_formatter import JavaFormatter
from aidl_gen.formatter.ndk_formatter import NDKFormatter
from aidl_gen.formatter.rust_formatter import RustFormatter
from aidl_gen.formatter.formatter import Formatter

def get_formatter(backend: Backend) -> Type[Formatter]:
    if backend == Backend.JAVA:
        return JavaFormatter
    elif backend == Backend.CPP:
        return CPPFormatter
    elif backend == Backend.NDK:
        return NDKFormatter
    elif backend == Backend.RUST:
        return RustFormatter

    raise NotImplementedError("Unknown backend")

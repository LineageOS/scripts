#
# Copyright (C) 2023 The LineageOS Project
#
# SPDX-License-Identifier: Apache-2.0
#

from typing import Type

from aidl_gen.aidl.backend import Backend
from aidl_gen.formatter.formatter import Formatter
from aidl_gen.formatter.cpp_formatter import CPPFormatter

def get_formatter(backend: Backend) -> Type[Formatter]:
    if backend == Backend.JAVA:
        raise NotImplementedError("Java backend is not implemented yet")
    elif backend == Backend.CPP:
        return CPPFormatter
    elif backend == Backend.NDK:
        raise NotImplementedError("NDK backend is not implemented yet")
    elif backend == Backend.RUST:
        raise NotImplementedError("Rust backend is not implemented yet")
    
    raise NotImplementedError("Unknown backend")

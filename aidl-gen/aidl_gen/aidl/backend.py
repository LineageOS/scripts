#
# Copyright (C) 2023 The LineageOS Project
#
# SPDX-License-Identifier: Apache-2.0
#

from enum import Enum

class Backend(Enum):
    JAVA = "java"
    CPP = "cpp"
    NDK = "ndk"
    RUST = "rust"

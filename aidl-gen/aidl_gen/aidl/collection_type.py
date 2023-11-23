#
# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0
#

from enum import Enum

class CollectionType(Enum):
    ARRAY = "T[]"
    LIST = "List<T>"
    FIXED_SIZE_ARRAY = "T[N]"

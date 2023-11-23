#
# Copyright (C) 2023 The LineageOS Project
#
# SPDX-License-Identifier: Apache-2.0
#

from typing import Optional, Union

from aidl_gen.aidl.collection_type import CollectionType
from aidl_gen.aidl.primitive_type import PrimitiveType

class DataType:
    """
    An AIDL data type for arguments and return values.

    Can reference another DataType (for nested collection types), or be a primitive type.
    """

    def __init__(
        self,
        data_type: Union[PrimitiveType, "DataType"],
        collection_type: Optional[CollectionType] = None,
    ):
        self.argument_type = data_type
        self.data_type = collection_type

    def is_primitive_type(self) -> bool:
        """Returns whether the argument is a primitive type."""
        return self.argument_type is PrimitiveType

    def is_collection_type(self) -> bool:
        """Returns whether the argument is a collection type."""
        return self.data_type is not None

    @classmethod
    def from_aidl(cls, data_type: str) -> "DataType":
        return cls(
            PrimitiveType(data_type),
        )

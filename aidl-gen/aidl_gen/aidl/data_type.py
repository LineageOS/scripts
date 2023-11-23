#
# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0
#

from typing import Dict, Optional, Union

from aidl_gen.aidl.collection_type import CollectionType
from aidl_gen.aidl.primitive_type import PrimitiveType

class DataType:
    """
    An AIDL data type for arguments and return values.

    Can reference another DataType (for nested collection types), or be a primitive type.
    """

    def __init__(
        self,
        data_type: Union[str, PrimitiveType, "DataType"],
        collection_type: Optional[CollectionType] = None,
        array_size: Optional[int] = None,
    ):
        self.data_type = data_type
        self.collection_type = collection_type
        self.array_size = array_size

        # Assert that array_size is only set for fixed size arrays and that is null for other types
        assert (self.array_size is None) == (
            self.collection_type != CollectionType.FIXED_SIZE_ARRAY
        ), f"Array size {self.array_size} is only valid for fixed size arrays"

    def is_primitive_type(self) -> bool:
        """Returns whether the argument is a primitive type."""
        return self.data_type in PrimitiveType

    def is_collection_type(self) -> bool:
        """Returns whether the argument is a collection type."""
        return self.collection_type is not None

    @classmethod
    def from_aidl(
        cls,
        data_type: str,
        imports: Optional[Dict[str, str]] = None,
    ) -> "DataType":
        assert data_type != "", "Empty data type"

        # Check syntax
        assert data_type.count("[") == data_type.count("]"), \
            f"Invalid syntax for data type {data_type}"
        assert data_type.count("<") == data_type.count(">"), \
            f"Invalid syntax for data type {data_type}"

        # Check for collection type
        if data_type.endswith("]"):
            # Find the first and last square brackets
            first_square_bracket = data_type.find("[")
            last_square_bracket = data_type.rfind("]")

            # Get the collection type
            collection_type = data_type[:first_square_bracket]

            # Check if this is a fixed size array
            if not data_type.endswith("[]"):
                # Get the array size
                array_size_str = data_type[first_square_bracket + 1:last_square_bracket].strip()

                # Check if the array size is valid
                assert array_size_str.isdigit(), f"Invalid array size {array_size_str}"

                array_size = int(array_size_str)

                # Check if the array size is zero
                assert array_size != 0, "Zero-length arrays are not supported"

                # Return the fixed size array
                return cls(
                    cls.from_aidl(collection_type),
                    CollectionType.FIXED_SIZE_ARRAY,
                    array_size,
                )
            else:
                return cls(
                    cls.from_aidl(collection_type, imports),
                    CollectionType.ARRAY,
                )

        if data_type.startswith("List<"):
            assert data_type.endswith(">"), f"Invalid syntax for data type {data_type}"

            return cls(
                cls.from_aidl(data_type[5:-1], imports),
                CollectionType.LIST,
            )

        # Should be a non-collection type, check if it's a primitive type
        primitive_type = PrimitiveType.from_value(data_type)
        if primitive_type:
            return cls(primitive_type)

        # Should be a non-primitive non-collection type, our last hope is that it's either a fqname
        # or it's mentioned in the imports
        if imports and data_type in imports:
            data_type = imports[data_type]

        assert "." in data_type, f"Found a non-fqname data type {data_type}"

        return cls(data_type)

#
# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0
#

from enum import Enum
from typing import Dict, List, Optional

from aidl_gen.aidl.annotation import Annotation
from aidl_gen.aidl.data_type import DataType
from aidl_gen.aidl.primitive_type import PrimitiveType

class MethodArgument:
    """An AIDL method's argument."""

    class Direction(Enum):
        """The direction of an argument."""

        IN = "in"
        OUT = "out"
        INOUT = "inout"

        @classmethod
        def from_value(cls, value: str) -> Optional["MethodArgument.Direction"]:
            try:
                return cls(value)
            except ValueError:
                return None

    def __init__(
        self,
        name: str,
        direction: Direction,
        data_type: DataType,
        annotations: Optional[List[Annotation]] = None,
    ):
        self.name = name
        self.direction = direction
        self.data_type = data_type
        self.annotations = annotations or []

    @classmethod
    def from_aidl(
        cls,
        argument: str,
        imports: Optional[Dict[str, str]] = None,
    ) -> "MethodArgument":
        """Creates an Argument from an AIDL string."""
        parts = argument.strip().split()

        assert len(parts) >= 2, f"Argument {argument} has less than 2 parts"

        name = parts.pop()

        data_type: Optional[DataType] = None
        direction = MethodArgument.Direction.IN
        annotations = []

        for part in parts:
            arg_dir = MethodArgument.Direction.from_value(part)
            if arg_dir:
                direction = arg_dir
                continue

            if part.startswith("@"):
                annotation = Annotation.from_aidl(part)

                assert annotation is not None, f"Invalid annotation {part}"

                annotations.append(annotation)

                continue

            assert data_type is None, \
                f"Argument data type for {name} is already set: {data_type}"

            data_type = DataType.from_aidl(part, imports)

            assert data_type.collection_type != PrimitiveType.VOID, \
                f"Argument {name} cannot be void"

        assert data_type is not None, f"Argument data type for {name} not found"

        return cls(
            name,
            direction,
            data_type,
            annotations,
        )

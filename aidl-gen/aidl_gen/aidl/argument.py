#
# Copyright (C) 2023 The LineageOS Project
#
# SPDX-License-Identifier: Apache-2.0
#

from typing import Optional, Set
from aidl_gen.aidl.annotation import Annotation
from aidl_gen.aidl.argument_direction import ArgumentDirection
from aidl_gen.aidl.data_type import DataType
from aidl_gen.aidl.primitive_type import PrimitiveType

class Argument:
    """An AIDL method's argument."""
    def __init__(
        self,
        name: str,
        argument_direction: ArgumentDirection,
        data_type: DataType,
        annotations: Optional[Set[Annotation]] = None,
    ):
        self.name = name
        self.argument_direction = argument_direction
        self.data_type = data_type
        self.annotations = annotations or set()

    @classmethod
    def from_aidl(cls, argument: str) -> "Argument":
        """Creates an Argument from an AIDL string."""
        parts = argument.strip().split()

        assert len(parts) >= 2, f"Argument {argument} has less than 2 parts"

        name = parts.pop()

        data_type: Optional[DataType] = None
        argument_direction = ArgumentDirection.IN
        annotations = set()

        for part in parts:
            if part in ArgumentDirection:
                argument_direction = ArgumentDirection(part)
            elif part.startswith("@"):
                annotations.add(Annotation(part))
            else:
                assert data_type is None, f"Argument data type for {name} is already set"

                data_type = DataType.from_aidl(part)

                assert data_type.data_type != PrimitiveType.VOID, f"Argument {name} cannot be void"

        assert data_type is not None, f"Argument data type for {name} not found"

        return cls(
            name=name,
            argument_direction=argument_direction,
            data_type=data_type,
            annotations=annotations,
        )

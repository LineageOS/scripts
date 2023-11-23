#
# Copyright (C) 2023 The LineageOS Project
#
# SPDX-License-Identifier: Apache-2.0
#

from typing import Dict, List, Optional, Set

from aidl_gen.aidl.annotation import Annotation
from aidl_gen.aidl.data_type import DataType
from aidl_gen.aidl.method_argument import MethodArgument

class Method:
    """An AIDL method, containing arguments."""
    def __init__(
        self,
        name: str,
        arguments: List[MethodArgument],
        return_type: DataType,
        annotations: Optional[List[Annotation]] = None,
    ):
        self.name = name
        self.arguments = arguments
        self.return_type = return_type
        self.annotations = annotations or []

    @classmethod
    def from_aidl(
        cls,
        method: str,
        imports: Optional[Dict[str, str]] = None,
    ) -> "Method":
        """Parses an AIDL method into a Method object."""
        # example: void teleport(Location baz, float speed);

        arguments: List[MethodArgument] = []
        return_type: Optional[DataType] = None
        annotations: List[Annotation] = []

        qualifiers, arguments_str = method.split("(", 1)
        arguments_str = arguments_str.removesuffix(")")

        qualifiers, name = qualifiers.rsplit(maxsplit=1)

        for qualifier in qualifiers.split():
            annotation: Optional[Annotation] = None
            try:
                annotation = Annotation.from_aidl(qualifier)
            except Exception:
                pass

            if annotation:
                annotations.append(annotation)
                continue

            assert return_type is None, f"Multiple return types found: {qualifiers}"

            return_type = DataType.from_aidl(qualifier, imports)

        assert return_type is not None, f"No return type found: {qualifiers}"

        for arg in arguments_str.split(","):
            arg = arg.strip()
            if arg == "":
                continue

            arguments.append(MethodArgument.from_aidl(arg, imports))

        return cls(
            name,
            arguments,
            return_type,
            annotations,
        )

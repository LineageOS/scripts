#
# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0
#

from enum import Enum
from typing import Dict, Optional

class Annotation:
    """An AIDL entity's annotation."""

    class Type(Enum):
        NULLABLE = "@nullable"
        UTF8_IN_CPP = "@utf8InCpp"
        VINTF_STABILITY = "@VintfStability"
        UNSUPPORTED_APP_USAGE = "@UnsupportedAppUsage"
        HIDE = "@Hide"
        BACKING = "@Backing"
        NDK_ONLY_STABLE_PARCELABLE = "@NdkOnlyStableParcelable"
        JAVA_ONLY_STABLE_PARCELABLE = "@JavaOnlyStableParcelable"
        JAVA_DERIVE = "@JavaDerive"
        JAVA_PASSTHROUGH = "@JavaPassthrough"
        FIXED_SIZE = "@FixedSize"
        DESCRIPTOR = "@Descriptor"

        @classmethod
        def from_value(cls, value: str) -> Optional["Annotation.Type"]:
            try:
                return cls(value)
            except ValueError:
                return None

    def __init__(
        self,
        annotation_type: Type,
        arguments: Optional[Dict[str, str]] = None,
    ):
        self.annotation_type = annotation_type
        self.arguments = arguments or {}

    @classmethod
    def from_aidl(cls, annotation: str) -> "Annotation":
        """Creates an Annotation from an AIDL string."""
        annotation = annotation.strip()

        assert annotation.count("(") == annotation.count(")"), \
            f"Annotation {annotation} has mismatched parentheses"

        annotation_type: Optional[Annotation.Type] = None
        arguments: Dict[str, str] = {}

        if "(" in annotation:
            annotation, arguments_str = annotation.split("(", 1)
            arguments_str = arguments_str.removesuffix(")")

            for arg in arguments_str.split(","):
                arg = arg.strip()
                if arg == "":
                    continue

                key, value = arg.split("=", 1)

                arguments[key.strip()] = value.strip()

        annotation_type = Annotation.Type.from_value(annotation)

        assert annotation_type is not None, f"Invalid annotation {annotation}"

        return cls(annotation_type, arguments)

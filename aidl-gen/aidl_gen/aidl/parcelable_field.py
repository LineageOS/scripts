#
# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0
#

from typing import Dict, List, Optional

from aidl_gen.aidl.annotation import Annotation
from aidl_gen.aidl.data_type import DataType

class ParcelableField:
    """An AIDL parcelable's field."""
    def __init__(
        self,
        name: str,
        data_type: DataType,
        default_value: Optional[str] = None,
        annotations: Optional[List[Annotation]] = None,
    ):
        self.name = name
        self.data_type = data_type
        self.default_value = default_value
        self.annotations = annotations or []

    @classmethod
    def from_aidl(
        cls,
        parcelable_field: str,
        imports: Optional[Dict[str, str]] = None,
    ) -> "ParcelableField":
        """Create a ParcelableField from an AIDL string."""
        name: Optional[str] = None
        data_type: Optional[DataType] = None
        default_value: Optional[str] = None
        annotations: List[Annotation] = []

        if "=" in parcelable_field:
            parcelable_field, default_value = parcelable_field.split("=", 1)
            parcelable_field = parcelable_field.strip()
            default_value = default_value.strip()

        for word in parcelable_field.split():
            if word.startswith("@"):
                annotation = Annotation.from_aidl(word)
                annotations.append(annotation)
                continue

            if data_type is None:
                data_type = DataType.from_aidl(word, imports)
                continue

            if name is None:
                name = word
                continue

            raise AssertionError(f'Parcelable field "{parcelable_field}" has too many words')

        assert name is not None, f'Parcelable field "{parcelable_field}" has no name'
        assert data_type is not None, f'Parcelable field "{parcelable_field}" has no data type'

        return cls(name, data_type, default_value, annotations)

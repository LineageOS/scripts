#
# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0
#

from typing import List, Optional

from aidl_gen.aidl.annotation import Annotation
from aidl_gen.aidl.custom_type import CustomType
from aidl_gen.aidl.parcelable_field import ParcelableField

class Parcelable(CustomType):
    """An AIDL parcelable."""
    def __init__(
        self,
        fqname: str,
        fields: Optional[List[ParcelableField]] = None,
        annotations: Optional[List[Annotation]] = None,
    ):
        super().__init__(fqname, annotations)

        self.fields = fields or []

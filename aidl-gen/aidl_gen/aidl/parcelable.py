#
# Copyright (C) 2023 The LineageOS Project
#
# SPDX-License-Identifier: Apache-2.0
#

from typing import List, Optional, Tuple
from aidl_gen.aidl.annotation import Annotation
from aidl_gen.aidl.custom_type import CustomType

from aidl_gen.aidl.data_type import DataType

class Parcelable(CustomType):
    """An AIDL parcelable."""
    def __init__(
        self,
        fqname: str,
        fields: List[Tuple[str, DataType]],
        annotations: Optional[List[Annotation]] = None,
    ):
        super().__init__(fqname, annotations)

        self.fields = fields

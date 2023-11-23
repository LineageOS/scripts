#
# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0
#

from typing import List, Optional

from aidl_gen.aidl.annotation import Annotation
from aidl_gen.aidl.custom_type import CustomType

class Enum(CustomType):
    """An AIDL enum definition."""
    def __init__(
        self,
        fqname: str,
        annotations: Optional[List[Annotation]] = None,
    ) -> None:
        super().__init__(fqname, annotations)

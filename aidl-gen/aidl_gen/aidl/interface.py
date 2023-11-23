#
# Copyright (C) 2023 The LineageOS Project
#
# SPDX-License-Identifier: Apache-2.0
#

from typing import List, Optional

from aidl_gen.aidl.annotation import Annotation
from aidl_gen.aidl.custom_type import CustomType
from aidl_gen.aidl.method import Method

class Interface(CustomType):
    """An AIDL interface, containing methods."""
    def __init__(
        self,
        fqname: str,
        methods: Optional[List[Method]] = None,
        oneway: bool = False,
        annotations: Optional[List[Annotation]] = None,
    ):
        super().__init__(fqname, annotations)

        self.methods = methods or []
        self.oneway = oneway

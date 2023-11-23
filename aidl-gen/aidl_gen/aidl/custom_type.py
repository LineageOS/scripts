#
# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0
#

from typing import List, Optional

from aidl_gen.aidl.annotation import Annotation

class CustomType:
    def __init__(
        self,
        fqname: str,
        annotations: Optional[List[Annotation]],
    ) -> None:
        self.fqname = fqname
        self.annotations = annotations or []

        assert "." in self.fqname, f"Name is not fully qualified: {self.fqname}"

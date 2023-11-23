#
# Copyright (C) 2023 The LineageOS Project
#
# SPDX-License-Identifier: Apache-2.0
#

from pathlib import Path
from typing import TYPE_CHECKING, Any, List
from aidl_gen.aidl.backend import Backend

from aidl_gen.aidl.interface import Interface

if TYPE_CHECKING:
    from aidl_gen.aidl.package import Package
else:
    Package = Any

class VersionedPackage:
    """A versioned AIDL HAL interface."""
    def __init__(
        self,
        package: Package,
        version: int,
    ) -> None:
        self.package = package
        self.version = version

        assert self.version in self.package.get_versions(), f"Version {self.version} not found in {self.package}"

    def get_src_path(self) -> Path:
        """Return the path to the interface source files."""
        return self.package.path / "aidl_api" / self.package.name / str(self.version)

    def get_aosp_library_name(self, backend: Backend) -> str:
        """Return the name of the AOSP library for this interface."""
        return self.package.get_aosp_library_name(backend, self.version)

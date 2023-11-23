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

class HALInterface:
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

    def get_interface(self, fqname: str, includes: List[Path]) -> Interface:
        """Return the interface with the given fully-qualified name."""
        assert fqname.startswith(f"{self.package.name}."), f"Interface {fqname} does not belong to {self.package}"

        split_fqname = fqname.split(".")

        interface_path = self.get_src_path()
        for name in split_fqname[:-1]:
            interface_path /= name

        interface_path /= f"{split_fqname[-1]}.aidl"

        assert interface_path.is_file(), f"Interface {fqname} not found in {self.package}"

        return Interface.from_aidl_file(fqname, interface_path, includes)

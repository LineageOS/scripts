#
# Copyright (C) 2023 The LineageOS Project
#
# SPDX-License-Identifier: Apache-2.0
#

from pathlib import Path
from typing import List, Set
from warnings import warn

from aidl_gen.aidl.backend import Backend
from aidl_gen.aidl.versioned_package import VersionedPackage

class Package:
    """
    An AIDL package.

    This is technically an AIDL interface, as in a collection of actual interfaces and types,
    thanks Google for the naming confusion.
    """

    VERSION_CURRENT = -1
    """Current not-frozen version of the package."""

    def __init__(
        self,
        name: str,
        path: Path,
    ):
        self.name = name
        self.path = path

        assert self.path.is_dir(), f"Path {self.path} does not exist"

    def get_versions(self) -> Set[int]:
        """Return the list of all available versions for this interface."""
        return set(
            int(path.name) if path.name != "current" else self.VERSION_CURRENT
            for path in (self.path / "aidl_api" / self.name).iterdir()
            if path.is_dir()
        )

    def get_versioned_package(self, version: int) -> VersionedPackage:
        """Return the interface for the given version."""
        assert version != self.VERSION_CURRENT, "Usage of current version is not supported"

        return VersionedPackage(self, version)

    def get_aosp_library_name(self, backend: Backend, version: int):
        if version is self.VERSION_CURRENT:
            warn("Usage of current version is discouraged, please use a frozen version instead")

            return f"{self.name}-{backend.value}"

        return f"{self.name}-V{version}-{backend.value}"

    @classmethod
    def find_package(cls, name: str, includes: List[Path]):
        for include in includes:
            if not (include / "aidl_api" / name).is_dir():
                continue

            return cls(name, include)

        raise FileNotFoundError(f"Could not find package in {includes}")

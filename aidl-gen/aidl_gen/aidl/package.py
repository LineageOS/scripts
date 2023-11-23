#
# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0
#

from pathlib import Path
from typing import List, Optional, Set
from warnings import warn

class Package:
    """
    An AIDL package.

    This is technically an AIDL interface, as in a collection of actual interfaces and types,
    thanks Google for the naming confusion.
    """

    VERSION_CURRENT = -1
    """Current non-frozen version of the package."""

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

    def get_src_path(self, version: Optional[int] = None) -> Path:
        """Return the path to the interface source files."""
        if version is None:
            warn("Usage of no version is discouraged, please use a frozen version instead")

            return self.path

        if version == self.VERSION_CURRENT:
            warn("Usage of current version is discouraged, please use a frozen version instead")

            return self.path / "aidl_api" / self.name / "current"

        return self.path / "aidl_api" / self.name / str(version)

    @classmethod
    def find_package(cls, name: str, includes: List[Path]):
        for include in includes:
            if not (include / "aidl_api" / name).is_dir():
                continue

            return cls(name, include)

        raise FileNotFoundError(f"Could not find package in {includes}")

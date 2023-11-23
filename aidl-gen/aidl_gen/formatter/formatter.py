#
# Copyright (C) 2023 The LineageOS Project
#
# SPDX-License-Identifier: Apache-2.0
#

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict

from aidl_gen.aidl.backend import Backend

if TYPE_CHECKING:
    from aidl_gen.aidl.versioned_package import VersionedPackage
    from aidl_gen.aidl.interface import Interface
    from aidl_gen.aidl.package import Package
else:
    VersionedPackage = Any
    Interface = Any
    Package = Any

LICENSE_HEADER_TEMPLATE = \
"""\
{comment_start}
{comment_middle}SPDX-FileCopyrightText: {year} The LineageOS Project
{comment_middle}SPDX-License-Identifier: Apache-2.0
{comment_end}
"""

INIT_RC_TEMPLATE = \
"""
service vendor.{hal_name}-default /vendor/bin/hw/{aidl_name}-service
    class hal
    user nobody
    group nobody
    shutdown critical
"""

VINTF_FRAGMENT_TEMPLATE = \
"""\
<manifest version="1.0" type="device">
    <hal format="aidl">
        <name>{aidl_name}</name>
        <version>{interface_version}</version>
        <fqname>{interface_name}/default</fqname>
    </hal>
</manifest>
"""

class Formatter:
    """Base class for all formatters."""

    BACKEND: Backend
    """The backend this formatter is for."""

    @classmethod
    def _dump_to_folder(
        cls,
        package: Package,
        interface: Interface,
        folder: Path,
        template_kwargs: Dict[str, str],
    ):
        raise NotImplementedError()

    @classmethod
    def dump_to_folder(
        cls,
        package: Package,
        hal_interface: VersionedPackage,
        interface: Interface,
        folder: Path
    ):
        assert folder.is_dir(), f"Path {folder} does not exist"

        aidl_name = package.name
        hal_name = aidl_name.rsplit('.', 1)[1]
        interface_name = interface.fqname.removeprefix(f"{aidl_name}.")
        class_name = interface_name.removeprefix("I")

        template_kwargs = {
            "aidl_name": aidl_name,
            "class_name": class_name,
            "class_name_lower": class_name.lower(),
            "hal_name": hal_name,
            "interface_aosp_library_name": hal_interface.get_aosp_library_name(cls.BACKEND),
            "interface_name": interface_name,
            "interface_version": hal_interface.version,
            "year": datetime.now().year,
        }

        # Write the common files
        (folder / f"{aidl_name}-service.rc").write_text(
            cls.format_template_with_license(INIT_RC_TEMPLATE, "//", "// ", "//", **template_kwargs)
        )
        (folder / f"{aidl_name}-service.xml").write_text(
            cls.format_template_with_license(VINTF_FRAGMENT_TEMPLATE, "<!--", "     ", "-->", **template_kwargs)
        )

        # Now let the backend-specific formatter do its things
        cls._dump_to_folder(package, interface, folder, template_kwargs)

    @classmethod
    def get_license_header(cls, comment_start: str, comment_middle: str, comment_end: str) -> str:
        year = datetime.now().year

        return LICENSE_HEADER_TEMPLATE.format(
            comment_start=comment_start,
            comment_middle=comment_middle,
            comment_end=comment_end,
            year=year,
        )

    @classmethod
    def format_template_with_license(
        cls, template: str, comment_start: str, comment_middle: str, comment_end: str, **kwargs
    ) -> str:
        return cls.get_license_header(comment_start, comment_middle, comment_end) + template.format(**kwargs)

#
# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0
#

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict

from aidl_gen.aidl.package import Package
from aidl_gen.formatter.backend import Backend
from aidl_gen.parser import Parser

if TYPE_CHECKING:
    from aidl_gen.aidl.interface import Interface
else:
    Interface = Any

LICENSE_HEADER_TEMPLATE = \
"""\
{comment_start}
{comment_middle}SPDX-FileCopyrightText: The LineageOS Project
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

    BLUEPRINT_COMMENT = ["//", "// ", "//"]
    CPP_COMMENT = ["/*", " * ", " */"]
    INIT_RC_COMMENT = ["#", "# ", "#"]
    XML_COMMENT = ["<!--", "    ", "-->"]

    @classmethod
    def _dump_to_folder(
        cls,
        package: Package,
        version: int,
        interface: Interface,
        parser: Parser,
        folder: Path,
        template_kwargs: Dict[str, Any],
    ) -> None:
        raise NotImplementedError()

    @classmethod
    def dump_to_folder(
        cls,
        package: Package,
        version: int,
        interface: Interface,
        parser: Parser,
        folder: Path,
    ):
        assert folder.is_dir(), f"Path {folder} does not exist"

        aidl_name = package.name
        hal_name = aidl_name.rsplit('.', 1)[1]
        interface_name = interface.fqname.removeprefix(f"{aidl_name}.")
        class_name = interface_name.removeprefix("I")

        target_name = f"{aidl_name}-service"

        init_rc_name = f"{target_name}.rc"
        vintf_fragment_name = f"{target_name}.xml"

        template_kwargs: Dict[str, Any] = {
            "aidl_name": aidl_name,
            "class_name": class_name,
            "hal_name": hal_name,
            "init_rc_name": init_rc_name,
            "interface_aosp_library_name": cls.BACKEND.get_aosp_library_name(package, version),
            "interface_name": interface_name,
            "interface_version": "current" if version == Package.VERSION_CURRENT else version,
            "target_name": target_name,
            "vintf_fragment_name": vintf_fragment_name,
        }

        # Write the common files
        (folder / init_rc_name).write_text(
            cls.format_template_with_license(
                INIT_RC_TEMPLATE, *cls.INIT_RC_COMMENT, **template_kwargs
            )
        )
        (folder / vintf_fragment_name).write_text(
            cls.format_template_with_license(
                VINTF_FRAGMENT_TEMPLATE, *cls.XML_COMMENT, **template_kwargs
            )
        )

        # Now let the backend-specific formatter do its things
        cls._dump_to_folder(package, version, interface, parser, folder, template_kwargs)

    @classmethod
    def get_license_header(
        cls,
        comment_start: str,
        comment_middle: str,
        comment_end: str,
    ) -> str:
        return LICENSE_HEADER_TEMPLATE.format(
            comment_start=comment_start,
            comment_middle=comment_middle,
            comment_end=comment_end,
        )

    @classmethod
    def format_template_with_license(
        cls,
        template: str,
        comment_start: str,
        comment_middle: str,
        comment_end: str,
        **kwargs: Any,
    ) -> str:
        return cls.get_license_header(
            comment_start, comment_middle, comment_end
        ) + template.format(**kwargs)

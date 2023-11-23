#
# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0
#
"""AIDL language parser."""

from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from aidl_gen.aidl.annotation import Annotation
from aidl_gen.aidl.enum import Enum
from aidl_gen.aidl.interface import Interface
from aidl_gen.aidl.method import Method
from aidl_gen.aidl.package import Package
from aidl_gen.aidl.parcelable import Parcelable
from aidl_gen.aidl.parcelable_field import ParcelableField

class Parser:
    COMMENT_LINE = "//"
    COMMENT_BLOCK_START = "/*"
    COMMENT_BLOCK_END = "*/"

    def __init__(
        self,
        include_folders: List[Path],
    ):
        self.include_folders = include_folders

        assert len(self.include_folders) > 0, "No import folder"

        self.imports_cache: Dict[
            Tuple[str, Optional[int]], Union[Enum, Interface, Parcelable]
        ] = {}
        """Cache for imports, (fqname, version) to AIDL entity."""

    def import_aidl(
        self,
        fqname: str,
        version: Optional[int] = None,
    ) -> Union[Enum, Interface, Parcelable]:
        if (fqname, version) in self.imports_cache:
            return self.imports_cache[(fqname, version)]

        # Check all the potential packages
        potential_packages = [
            fqname.rsplit(".", i)[0]
            for i in range(1, fqname.count(".") + 1)
        ]

        for include_folder in self.include_folders:
            for package in potential_packages:
                package_folder = include_folder

                # Get a specific version if asked for, else use the unfrozen version
                if version is not None:
                    package_folder = package_folder / "aidl_api" / package

                    if version == Package.VERSION_CURRENT:
                        package_folder = package_folder / "current"
                    else:
                        package_folder = package_folder / str(version)

                for package_folder_name in package.split("."):
                    package_folder = package_folder / package_folder_name

                if not package_folder.is_dir():
                    continue

                # Check if we got a package name instead
                if fqname == package:
                    continue

                # Now get all the possible subpackages to support nested declarations
                remaining_package = fqname[len(package) + 1:]
                potential_subpackages = [
                    remaining_package.rsplit(".", i)[0]
                    for i in range(remaining_package.count(".") + 1)
                ]

                # Now search for an .aidl file that matches the subpackage
                for potential_subpackage in potential_subpackages:
                    aidl_file = package_folder
                    split_str = potential_subpackage.split(".")
                    for subpackage in split_str[:-1]:
                        aidl_file = aidl_file / subpackage

                    aidl_file = aidl_file / f"{split_str[-1]}.aidl"
                    if not aidl_file.is_file():
                        continue

                    aidl_entity = self.parse(aidl_file)

                    assert aidl_entity.fqname == fqname, \
                        f"Found {aidl_entity.fqname} instead of {fqname}"
                    
                    self.imports_cache[(fqname, version)] = aidl_entity

                    return aidl_entity

        raise Exception(f"Could not find {fqname} (version {version}), missing include folder?")

    def parse(self, aidl_file: Path) -> Union[Enum, Interface, Parcelable]:
        local_imports: Dict[str, str] = {}
        package_name: Optional[str] = None
        in_comment_block = False
        inside_type_definition = False
        relative_name: Optional[str] = None
        annotations: List[Annotation] = []

        parsed_block = ""

        # Enum
        is_enum = False

        # Interface
        is_interface = False
        interface_methods: List[Method] = []
        interface_oneway = False

        # Parcelable
        is_parcelable = False
        parcelable_fields: List[ParcelableField] = []

        for line_number, line in enumerate(aidl_file.read_text().splitlines(), 1):
            line = line.strip()

            # If we are inside a comment block, check if we have a comment block end
            # and keep that comes after it
            while self.COMMENT_BLOCK_START in line or self.COMMENT_BLOCK_END in line:
                if self.COMMENT_BLOCK_END in line:
                    assert in_comment_block or self.COMMENT_BLOCK_START in line, \
                        self._format_error_message(
                            aidl_file, line, line_number, "Invalid comment block end"
                        )

                    in_comment_block = False
                    line = line.split(self.COMMENT_BLOCK_END, 1)[1]
                elif self.COMMENT_BLOCK_START in line and not in_comment_block:
                    in_comment_block = True

                    if self.COMMENT_BLOCK_END in line:
                        line = line.split(self.COMMENT_BLOCK_END, 1)[1]
                    else:
                        line = ""

            if in_comment_block:
                continue

            # Get rid of anything after "//" if we aren't inside a comment block
            if not in_comment_block and self.COMMENT_LINE in line:
                line = line.split(self.COMMENT_LINE, 1)[0]

            # Skip empty lines
            if not line:
                continue

            if line.startswith("package "):
                assert package_name is None, self._format_error_message(
                    aidl_file, line, line_number, "Multiple package names"
                )

                package_name = line.split()[1].removesuffix(";")

                continue

            assert package_name, \
                self._format_error_message(aidl_file, line, line_number, "Package name not found")

            if line.startswith("import "):
                assert line.endswith(";"), \
                    self._format_error_message(aidl_file, line, line_number, "Missing semicolon")

                import_name = line.split()[1].removesuffix(';')

                if "." not in import_name:
                    # It's a relative import
                    import_name = f"{package_name}.{import_name}"

                # Save the imports, they will be used later
                # to figure out fqnames
                local_imports[import_name.split(".")[-1]] = import_name

                continue

            while line.startswith("@"):
                split_line = line.split(" ", 1)
                if len(split_line) == 1:
                    # It's a single annotation
                    split_line = split_line[0], ""

                annotation_value, line = split_line
                line = split_line[1].strip()

                annotation = Annotation.from_aidl(annotation_value.strip())
                assert annotation is not None, self._format_error_message(
                    aidl_file, line, line_number, f"Unknown annotation {annotation_value}"
                )

                annotations.append(annotation)

            # Skip empty lines
            if not line:
                continue

            if line.startswith("enum ") \
                    or line.startswith("interface ") \
                    or line.startswith("oneway interface ") \
                    or line.startswith("parcelable "):
                if inside_type_definition:
                    raise AssertionError("Found nested declarations")

                inside_type_definition = True

                if line.startswith("enum "):
                    is_enum = True
                elif line.startswith("interface "):
                    is_interface = True
                elif line.startswith("oneway interface "):
                    is_interface = True
                    interface_oneway = True
                    line = line.removeprefix("oneway ")
                elif line.startswith("parcelable "):
                    is_parcelable = True

                assert relative_name is None, self._format_error_message(
                    aidl_file, line, line_number, "Found multiple structures"
                )

                relative_name = line.split()[1]

                continue

            if inside_type_definition:
                # If we reached end of interface declaration exit
                if line[0] == '}':
                    assert parsed_block == "", self._format_error_message(
                        aidl_file, line, line_number, f"Missing semicolon for {parsed_block}"
                    )

                    inside_type_definition = False

                    continue

                parsed_block += line

                if (is_interface or is_parcelable) and parsed_block.endswith(";"):
                    parsed_block = parsed_block.removesuffix(";")

                    if is_interface:
                        assert '(' in parsed_block, self._format_error_message(
                            aidl_file, line, line_number,
                            f"Unknown data inside interface: {line}"
                        )

                        # This should be a method
                        assert parsed_block.endswith(")"), \
                            f"Invalid syntax for method {parsed_block}"

                        interface_methods.append(Method.from_aidl(parsed_block, interface_oneway, local_imports))
                    elif is_parcelable:
                        if parsed_block.startswith("const "):
                            # This is a constant, can be ignored
                            pass
                        else:
                            try:
                                parcelable_fields.append(
                                    ParcelableField.from_aidl(parsed_block, local_imports)
                                )
                            except Exception as e:
                                raise Exception(
                                    self._format_error_message(
                                        aidl_file, line, line_number, str(e)
                                    )
                                )

                    parsed_block = ""
                elif is_enum and parsed_block.endswith(","):
                    parsed_block = ""

                continue

            raise Exception(
                self._format_error_message(
                    aidl_file, line, line_number, f"Unknown declaration: {line}"
                )
            )

        assert parsed_block == "", self._format_error_message(
            aidl_file, "", 1, f"Missing semicolon for {parsed_block}"
        )

        assert package_name, "Package name not found"

        assert relative_name, "Relative name not found"

        fqname = f"{package_name}.{relative_name}"

        if is_enum:
            return Enum(fqname, annotations=annotations)
        elif is_interface:
            return Interface(fqname, methods=interface_methods, annotations=annotations)
        elif is_parcelable:
            return Parcelable(fqname, fields=parcelable_fields, annotations=annotations)

        raise Exception(f"Unknown structure {fqname}")

    def _format_error_message(self, file: Path, line: str, line_number: int, message: str):
        return "\n".join([
            "",
            f"In file {file}, line {line_number}:",
            f"{line}",
            f"Error: {message}",
        ])

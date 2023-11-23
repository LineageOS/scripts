#
# Copyright (C) 2023 The LineageOS Project
#
# SPDX-License-Identifier: Apache-2.0
#

from pathlib import Path
from typing import Dict, List, Optional, Union

from aidl_gen.aidl.annotation import Annotation
from aidl_gen.aidl.enum import Enum
from aidl_gen.aidl.interface import Interface
from aidl_gen.aidl.method import Method
from aidl_gen.aidl.package import Package
from aidl_gen.aidl.parcelable import Parcelable
from aidl_gen.aidl.versioned_package import VersionedPackage

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

        self.imports_cache: Dict[str, Union[Interface, Parcelable]] = {}

    def import_aidl(
        self,
        fqname: str,
        version: Optional[int] = None,
    ) -> Optional[Union[Enum, Interface, Parcelable]]:
        # For all the example, we consider fqname = "android.hardware.light.ILights"

        if fqname in self.imports_cache:
            return self.imports_cache[fqname]

        # Check all the potential packages, so:
        # android.hardware.light
        # android.hardware
        # android
        potential_packages: List[str] = []
        for i in reversed(range(1, fqname.count(".") + 1)):
            potential_packages.append(fqname.rsplit(".", i)[0])

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

                print(package_folder)

                # Now get all the possible subpackages to support nested declarations, so:
                # ILights
                # light.ILights
                # hardware.light.ILights
                remaining_package = fqname[len(package) + 1:]
                print(remaining_package)
                potential_subpackages: List[str] = []
                for i in reversed(range(remaining_package.count(".") + 1)):
                    potential_subpackages.append(remaining_package.rsplit(".", i)[0])

                print(potential_subpackages)

                # Now search for an .aidl file
                # android/hardware/light/ILights.aidl
                # android/hardware/light.aidl
                for potential_subpackage in potential_subpackages:
                    aidl_file = package_folder
                    split_str = potential_subpackage.split(".")
                    for subpackage in split_str[:-1]:
                        aidl_file = aidl_file / subpackage

                    aidl_file = aidl_file / f"{split_str[-1]}.aidl"
                    print(aidl_file)
                    if not aidl_file.is_file():
                        continue

                    return self.parse(aidl_file)

        return None

    def parse(self, aidl_file: Path) -> Union[Enum, Interface, Parcelable]:
        package_name: Optional[str] = None
        in_comment_block = False
        inside_structure = False
        relative_name: Optional[str] = None
        annotations: List[Annotation] = []

        parsed_block = ""

        # Enum
        is_enum = False

        # Interface
        is_interface = False
        interface_methods: List[Method] = []
        parsing_function = False

        # Parcelable
        is_parcelable = False

        for line_number, line in enumerate(aidl_file.read_text().splitlines(), 1):
            line = line.strip()

            # If we are inside a comment block, check if we have a comment block end
            # and keep that comes after it
            while self.COMMENT_BLOCK_START in line or self.COMMENT_BLOCK_END in line:
                if self.COMMENT_BLOCK_END in line:
                    assert in_comment_block or self.COMMENT_BLOCK_START in line, \
                        self._format_error_message(aidl_file, line, line_number, "Invalid comment block end")

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
                package_name = line.split()[1].removesuffix(";")
                continue

            assert package_name, self._format_error_message(aidl_file, line, line_number, "Package name not found")

            if line.startswith("import "):
                # Save the imports, they will be used in the code
                # to know from where data types comes from
                # and what data type it is
                import_name = line.split()[1].removesuffix(';')

                if "." not in import_name:
                    # It's a relative import
                    import_name = f"{package_name}.{import_name}"

                """
                assert import_name != fqname, \
                    self._format_error_message(line, line_number, "Circular import")
                """

                import_object = self.import_aidl(import_name)
                assert import_object is not None, \
                    self._format_error_message(aidl_file, line, line_number, f"Cannot import {import_name}")

                continue

            while line.startswith("@"):
                split_line = line.split(" ", 1)
                if len(split_line) == 1:
                    # It's a single annotation
                    split_line = split_line[0], ""

                annotation_value, line = split_line
                line = split_line[1].strip()

                annotation = Annotation.from_value(annotation_value.strip())
                assert annotation is not None, \
                    self._format_error_message(aidl_file, line, line_number, f"Unknown annotation {annotation_value}")

                annotations.append(annotation)
            
            # Skip empty lines
            if not line:
                continue

            if line.startswith("enum "):
                if inside_structure:
                    raise AssertionError("Found nested declarations")

                inside_structure = True

                is_enum = True

                assert relative_name is None, \
                    self._format_error_message(aidl_file, line, line_number, "Found multiple structures")

                relative_name = line.split()[1]

                continue

            if line.startswith("interface "):
                if inside_structure:
                    raise AssertionError("Found nested declarations")

                inside_structure = True

                is_interface = True

                assert relative_name is None, \
                    self._format_error_message(aidl_file, line, line_number, "Found multiple structures")

                relative_name = line.split()[1]

                continue

            if line.startswith("parcelable "):
                if inside_structure:
                    raise AssertionError("Found nested declarations")

                inside_structure = True

                is_parcelable = True

                assert relative_name is None, \
                    self._format_error_message(aidl_file, line, line_number, "Found multiple structures")

                relative_name = line.split()[1]

                continue

            if inside_structure:
                # If we reached end of interface declaration exit
                if line[0] == '}':
                    inside_structure = False
                    continue

                if is_enum:
                    continue

                if is_interface:
                    assert parsing_function or '(' in line, \
                        self._format_error_message(aidl_file, line, line_number, f"Unknown data inside interface: {line}")

                    # This should be a method (can span multiple lines)
                    parsing_function = True

                    parsed_block += line

                    if not line.endswith(","):
                        assert parsed_block.endswith(");"), f"Invalid syntax for method {parsed_block}"

                        parsed_block = parsed_block.removesuffix(";")
                        interface_methods.append(Method.from_aidl(parsed_block))
                        parsed_block = ""

                    continue

                if is_parcelable:
                    continue

            raise Exception(self._format_error_message(aidl_file, line, line_number, f"Unknown declaration: {line}"))

        assert package_name, "Package name not found"

        assert relative_name, "Relative name not found"

        fqname = f"{package_name}.{relative_name}"

        if is_enum:
            return Enum(fqname, annotations)
        elif is_interface:
            return Interface(fqname, interface_methods, annotations)
        elif is_parcelable:
            return Parcelable(fqname, [], annotations)

        raise Exception(f"Unknown structure {fqname}")

    def _format_error_message(self, file: Path, line: str, line_number: int, message: str):
        return "\n".join([
            "",
            f"Line {line_number}:",
            f"{line}",
            f"{message}",
        ])

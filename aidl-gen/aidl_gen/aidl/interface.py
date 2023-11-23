#
# Copyright (C) 2023 The LineageOS Project
#
# SPDX-License-Identifier: Apache-2.0
#

from typing import Dict, List
from pathlib import Path

from aidl_gen.aidl.method import AIDLMethod, Method

class Interface:
    """An AIDL interface, containing methods."""
    def __init__(
        self,
        fqname: str,
        methods: List[Method],
    ):
        self.fqname = fqname
        self.methods = methods

    @classmethod
    def from_aidl(cls, file: Path, includes: List[Path]) -> "Interface":
        open_comment = False
        inside_structure = False
        method = ""
        methods: List[Method] = []
        imports: Dict[str, Interface] = {}

        content = file.read_text()

        for line in content.splitlines():
            line = line.strip()

            # Skip empty lines
            if not line:
                continue

            # Deal with comments, we relay on the .aidl
            # not having comments in the middle of the code
            if open_comment:
                if "*/" in line:
                    open_comment = False
                continue

            if line.startswith("/*"):
                open_comment = True
                continue

            if line.startswith("import"):
                # Save the imports, they will be used in the code
                # to know from where data types comes from
                # and what data type it is
                import_name = line.split()[1].removesuffix(';')
                imports[import_name.rsplit('.', 1)[1]] = Interface.from_aidl(file, includes)
                continue

            if line.startswith("interface"):
                if inside_structure:
                    raise AssertionError("Found nested declarations")
                inside_structure = True
                continue

            if inside_structure:
                # If we reached end of interface declaration exit
                if line[0] == '}':
                    inside_structure = False
                    continue

                # Skip non functions
                if not '(' in line and not line.startswith("in"):
                    continue

                # This should be a method (can span multiple lines)
                if line.endswith(","):
                    method += line
                else:
                    methods.append(Method.from_aidl(method + line))
                    method = ""
                continue

        return cls(file.stem, methods)

class AIDLInterface:
    def __init__(self, fqname: str, includes: list[Path]):
        self.fqname = fqname
        self.includes = includes

        self.interface_file = self.get_aidl_file(self.fqname)

        self.methods: List[AIDLMethod] = []
        self.imports: Dict[str, AIDLInterface] = {}
        self.is_interface = False
        self.is_parcelable = False

        open_comment = False
        inside_structure = False
        self.method = ""

        self.content = self.interface_file.read_text()
        for line in self.content.splitlines():
            line = line.strip()

            # Skip empty lines
            if not line:
                continue

            # Deal with comments, we relay on the .aidl
            # not having comments in the middle of the code
            if open_comment:
                if "*/" in line:
                    open_comment = False
                continue

            if line.startswith("/*"):
                open_comment = True
                continue

            if line.startswith("import"):
                # Save the imports, they will be used in the code
                # to know from where data types comes from
                # and what data type it is
                import_name = line.split()[1].removesuffix(';')
                self.imports[import_name.rsplit('.', 1)[1]] = AIDLInterface(import_name, includes)
                continue

            if line.startswith("interface") or line.startswith("parcelable"):
                if inside_structure:
                    raise AssertionError("Found nested declarations")
                inside_structure = True
                if line.startswith("interface"):
                    self.is_interface = True
                elif line.startswith("parcelable"):
                    self.is_parcelable = True
                continue

            if inside_structure:
                # If we reached end of interface declaration exit
                if line[0] == '}':
                    inside_structure = False
                    continue

                if self.is_interface:
                    # Skip non functions
                    if not '(' in line and not line.startswith("in"):
                        continue

                    # This should be a method (can span multiple lines)
                    if line.endswith(","):
                        self.method += line
                    else:
                        self.methods.append(AIDLMethod(self.method + line, self.imports))
                        self.method = ""
                    continue

    def get_aidl_file(self, fqname: str):
        for dir in self.includes:
            file = dir / Path(fqname.replace('.', '/') + '.aidl')
            if not file.is_file():
                continue
            return file

        raise FileNotFoundError(f"Interface {fqname} not found")

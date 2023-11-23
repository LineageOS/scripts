#
# Copyright (C) 2023 The LineageOS Project
#
# SPDX-License-Identifier: Apache-2.0
#

from typing import List, Optional, Set
from aidl_gen.aidl.annotation import Annotation
from aidl_gen.aidl.argument import Argument
from aidl_gen.aidl.data_type import DataType
from aidl_gen.formatter.cpp import AIDL_TO_CPP_TYPE

class Method:
    """An AIDL method, containing arguments."""
    def __init__(
        self,
        name: str,
        arguments: List[Argument],
        return_type: DataType,
        annotations: Optional[Set[Annotation]] = None,
    ):
        self.name = name
        self.arguments = arguments
        self.return_type = return_type
        self.annotations = annotations or set()

    @classmethod
    def from_aidl(cls, method_str: str) -> "Method":
        """Parses an AIDL method into a Method object."""
        # example: void teleport(Location baz, float speed);

        return_type: Optional[DataType] = None
        annotations = set()

        qualifiers, arguments = method_str.split("(", 1)
        arguments = arguments.removesuffix(")")

        qualifiers, name = qualifiers.rsplit(maxsplit=1)

        for qualifier in qualifiers.split():
            if qualifier in Annotation:
                annotations.add(Annotation[qualifier])
            else:
                assert return_type is None, f"Multiple return types found: {qualifiers}"

                return_type = DataType.from_aidl(qualifier)

        assert return_type is not None, f"No return type found: {qualifiers}"

        return cls(
            name,
            [Argument.from_aidl(arg.strip()) for arg in arguments.split(",")],
            return_type,
            annotations,
        )

class AIDLMethodArgument:
    def __init__(self, argument: str, imports: dict, aidl_return: bool = False):
        self.argument = argument
        self.imports = imports
        self.aidl_return = aidl_return
        self.nullable = False

        args = self.argument.split()
        if len(args) > 2:
            self.nullable = True
            self.arg_type = args[1]
            self.name = args[2]
        else:
            self.arg_type = args[0]
            self.name = args[1]

        self.data_type = self.get_type()
        self.is_array = self.get_is_array()

        if self.data_type in AIDL_TO_CPP_TYPE:
            self.data_type = AIDL_TO_CPP_TYPE[self.data_type]

        if self.is_array:
            self.arg_type = f"std::vector<{self.data_type}>"
        else:
            self.arg_type = self.data_type

        if self.data_type in imports and imports[self.data_type].is_interface:
            self.arg_type = f"std::shared_ptr<{self.arg_type}>"

        if self.data_type in imports and not aidl_return:
            if imports[self.data_type].is_interface or imports[self.data_type].is_parcelable:
                if self.nullable:
                    self.arg_type = f"std::optional<{self.arg_type}>"
                self.arg_type = f"const {self.arg_type}&"

        if self.aidl_return:
            self.arg_type += "*"

    def get_type(self):
        if self.arg_type.endswith("[]"):
            return self.arg_type.removesuffix("[]")
        if self.arg_type.startswith("List<"):
            return self.arg_type.removeprefix('List<').removesuffix('>')
        if self.arg_type.startswith("std::vector<"):
            return self.arg_type.removeprefix('std::vector<').removesuffix('>')
        return self.arg_type

    def get_is_array(self):
        return (self.arg_type.endswith("[]")
                or self.arg_type.startswith("List<")
                or self.arg_type.startswith("std::vector<"))

class AIDLMethod:
    def __init__(self, method_str: str, imports: dict):
        self.method_str = method_str

        self.args = []

        # We don't care about the method being oneway
        self.method_str = self.method_str.removeprefix("oneway ")

        self.return_type, temp = self.method_str.split(maxsplit=1)
        temp = temp.removesuffix(';')
        self.name, self.args_str = temp.split('(', 1)
        self.args_str = '(' + self.args_str

        self.args_str = self.args_str.removeprefix('(').removesuffix(')')

        if self.args_str != "":
            for arg in self.args_str.split(','):
                arg = arg.strip().removeprefix("in").strip()
                self.args.append(AIDLMethodArgument(arg, imports))

        if self.return_type != "void":
            self.args.append(AIDLMethodArgument(f"{self.return_type}  _aidl_return",
                                                imports, aidl_return=True))

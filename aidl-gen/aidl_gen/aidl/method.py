AIDL_TO_CPP_TYPE = {
    "boolean": "bool",
    "int": "int32_t",
}

class AIDLMethodArgument:
    def __init__(self, argument: str, aidl_return: bool = False):
        self.arg_type, self.name = argument.split()

        if self.arg_type.removesuffix("[]") in AIDL_TO_CPP_TYPE:
            if self.arg_type.endswith("[]"):
                self.arg_type = AIDL_TO_CPP_TYPE[self.arg_type.removesuffix("[]")] + "[]"
            else:
                self.arg_type = AIDL_TO_CPP_TYPE[self.arg_type.removesuffix("[]")]

        if self.arg_type.endswith("[]"):
            self.arg_type = f"std::vector<{self.arg_type.removesuffix('[]')}>"

        if aidl_return:
            self.arg_type += "*"

    def format(self):
        return f"{self.arg_type} {self.name}"

class AIDLMethod:
    def __init__(self, method_str: str):
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
                self.args.append(AIDLMethodArgument(arg))

        if self.return_type != "void":
            self.args.append(AIDLMethodArgument(f"{self.return_type}  _aidl_return",
                                                aidl_return=True))

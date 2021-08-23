# Source: https://source.android.com/devices/architecture/aidl/aidl-backends#types
AIDL_TO_CPP_TYPE = {
    "boolean": "bool",
    "byte": "int8_t",
    "char": "char16_t",
    "int": "int32_t",
    "long": "int64_t",
    # "float": "float", # No intervention required
    # "double": "double", # No intervention required
    "String": "::android::String16",
    "android.os.Parcelable": "::android::Parcelable",
    "IBinder": "::android::IBinder",
    # "T[]": "std::vector<T>", # Dealt with in AIDLMethodArgument
    # "byte[]": "std::vector<uint8_t>", # "byte" match will handle this
    # "List<T>": "std::vector<T>", # Dealt with in AIDLMethodArgument
    "FileDescriptor": "::android::base::unique_fd",
    "ParcelFileDescriptor": "::android::os::ParcelFileDescriptor",
    # "interface type (T)": "::android::sp<T>", # Dealt with in AIDLMethodArgument
    # "parcelable type (T)": "T", # No intervention required
    # "union type (T)": "T", # No intervention required
}

class AIDLMethodArgument:
    def __init__(self, argument: str, imports: dict, aidl_return: bool = False):
        self.argument = argument
        self.imports = imports
        self.aidl_return = aidl_return

        self.arg_type, self.name = self.argument.split()

        self.data_type = self.get_type()
        self.is_array = self.get_is_array()

        if self.data_type in AIDL_TO_CPP_TYPE:
            self.data_type = AIDL_TO_CPP_TYPE[self.data_type]

        if self.is_array:
            if (self.data_type in imports
                and imports[self.data_type].is_parcelable
                and not aidl_return):
                self.arg_type = f"const std::vector<{self.data_type}>&"
            else:
                self.arg_type = f"std::vector<{self.data_type}>"
        else:
            self.arg_type = self.data_type

        if self.data_type in imports and imports[self.data_type].is_interface:
                self.arg_type = f"const std::shared_ptr<{self.arg_type}>&"

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

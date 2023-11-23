#
# Copyright (C) 2023 The LineageOS Project
#
# SPDX-License-Identifier: Apache-2.0
#

from datetime import datetime
from pathlib import Path

from aidl_gen.formatter.cpp_formatter import (
    ANDROID_BP_TEMPLATE,
    MAIN_CPP_TEMPLATE,
    MAIN_H_TEMPLATE,
    SERVICE_CPP_TEMPLATE,
)
from aidl_gen.formatter.formatter import (
    INIT_RC_TEMPLATE,
    VINTF_FRAGMENT_TEMPLATE,
)

class AIDLService:
    def __init__(self, fqname: str, includes: list[Path]):
        self.fqname = fqname
        self.includes = includes

        self.aidl_name, self.interface_name = self.fqname.rsplit('.', 1)
        self.hal_name = self.aidl_name.rsplit('.', 1)[1]
        self.class_name = self.interface_name.removeprefix("I")
        self.class_name_lower = self.class_name.lower()
        self.aidl_namespace = self.aidl_name.replace('.', "::")
        self.aidl_path = self.aidl_name.replace('.', "/")
        self.aidl_namespace_open = "\n".join([f"namespace {namespace} {{"
                                              for namespace in self.aidl_name.split('.')])
        self.aidl_namespace_close = "\n".join([f"}} // namespace {namespace}"
                                               for namespace in self.aidl_name.split('.')[::-1]])
        self.year = datetime.now().year

        self.interface = AIDLInterface(self.fqname, self.includes)

    def write_to_folder(self, dir: Path):
        dir.mkdir(exist_ok=True)
        open(dir / "Android.bp", 'w').write(self.get_android_bp())
        open(dir / f"{self.aidl_name}-service.rc", 'w').write(self.get_init_rc())
        open(dir / f"{self.aidl_name}-service.xml", 'w').write(self.get_vintf_fragment())
        open(dir / f"{self.class_name}.cpp", 'w').write(self.get_main_cpp())
        open(dir / f"{self.class_name}.h", 'w').write(self.get_main_h())
        open(dir / "service.cpp", 'w').write(self.get_service_cpp())

    def get_android_bp(self):
        return ANDROID_BP_TEMPLATE.format(year=self.year,
                                          aidl_name=self.aidl_name,
                                          class_name=self.class_name)

    def get_init_rc(self):
        return INIT_RC_TEMPLATE.format(hal_name=self.hal_name,
                                       aidl_name=self.aidl_name)

    def get_vintf_fragment(self):
        return VINTF_FRAGMENT_TEMPLATE.format(aidl_name=self.aidl_name,
                                              interface_name=self.interface_name)

    def get_main_cpp(self):
        return MAIN_CPP_TEMPLATE.format(year=self.year,
                                        class_name=self.class_name,
                                        aidl_namespace_open=self.aidl_namespace_open,
                                        methods_definitions=self._format_methods_definitions(),
                                        aidl_namespace_close=self.aidl_namespace_close)

    def get_main_h(self):
        return MAIN_H_TEMPLATE.format(year=self.year,
                                      aidl_path=self.aidl_path,
                                      class_name=self.class_name,
                                      aidl_namespace_open=self.aidl_namespace_open,
                                      using_namespaces=self._format_using_namespaces(),
                                      methods_declarations=self._format_methods_declarations(),
                                      aidl_namespace_close=self.aidl_namespace_close)

    def get_service_cpp(self):
        return SERVICE_CPP_TEMPLATE.format(year=self.year,
                                           class_name=self.class_name,
                                           aidl_namespace=self.aidl_namespace,
                                           class_name_lower=self.class_name_lower)

    def _format_using_namespaces(self):
        result = []
        for import_types in self.interface.imports.values():
            result.append(f"using ::aidl::{import_types.fqname.replace('.', '::')};")

        return "\n".join(result)

    def _format_methods_definitions(self):
        result = []
        for method in self.interface.methods:
            args_formatted = ", ".join([f"{arg.arg_type} /*{arg.name}*/" for arg in method.args])
            result.append(f"ndk::ScopedAStatus {self.class_name}::{method.name}({args_formatted}) {{\n"
                          f"    return ndk::ScopedAStatus::fromExceptionCode(EX_UNSUPPORTED_OPERATION);\n"
                          f"}}")

        return "\n\n".join(result)

    def _format_methods_declarations(self):
        result = []
        for method in self.interface.methods:
            args_formatted = ", ".join([f"{arg.arg_type} {arg.name}" for arg in method.args])
            result.append(f"    ndk::ScopedAStatus {method.name}({args_formatted}) override;")

        return "\n".join(result)

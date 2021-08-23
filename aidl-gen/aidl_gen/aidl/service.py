from aidl_gen.aidl.interface import AIDLInterface
from datetime import datetime
from pathlib import Path

ANDROID_BP_TEMPLATE = \
"""\
//
// Copyright (C) {year} The LineageOS Project
//
// SPDX-License-Identifier: Apache-2.0
//

cc_binary {{
    name: "{aidl_name}-service",
    relative_install_path: "hw",
    init_rc: ["{aidl_name}-service.rc"],
    vintf_fragments: ["{aidl_name}-service.xml"],
    srcs: [
        "{class_name}.cpp",
        "service.cpp",
    ],
    shared_libs: [
        "libbinder_ndk",
        "{aidl_name}-ndk_platform",
    ],
    vendor: true,
}}
"""

INIT_RC_TEMPLATE = \
"""\
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
        <fqname>{interface_name}/default</fqname>
    </hal>
</manifest>
"""

MAIN_CPP_TEMPLATE = \
"""\
/*
 * Copyright (C) {year} The LineageOS Project
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "{class_name}.h"

namespace aidl {{
{aidl_namespace_open}

{methods_definitions}

{aidl_namespace_close}
}} // namespace aidl
"""

MAIN_H_TEMPLATE = \
"""\
/*
 * Copyright (C) {year} The LineageOS Project
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#pragma once

#include <aidl/{aidl_path}/Bn{class_name}.h>

namespace aidl {{
{aidl_namespace_open}

{using_namespaces}
class {class_name} : public Bn{class_name} {{
public:
{methods_declarations}
}};

{aidl_namespace_close}
}} // namespace aidl
"""

SERVICE_CPP_TEMPLATE = \
"""\
/*
 * Copyright (C) {year} The LineageOS Project
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "{class_name}.h"

#include <android/binder_manager.h>
#include <android/binder_process.h>

using ::aidl::{aidl_namespace}::{class_name};

int main() {{
    ABinderProcess_setThreadPoolMaxThreadCount(0);
    std::shared_ptr<{class_name}> {class_name_lower} = ndk::SharedRefBase::make<{class_name}>();

    const std::string instance = std::string() + {class_name}::descriptor + "/default";
    binder_status_t status = AServiceManager_addService({class_name_lower}->asBinder().get(), instance.c_str());
    CHECK(status == STATUS_OK);

    ABinderProcess_joinThreadPool();
    return EXIT_FAILURE; // should not reach
}}
"""

class AIDLService:
    def __init__(self, fqname: str, include_dir: Path):
        self.fqname = fqname
        self.include_dir = include_dir

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

        self.interface = AIDLInterface(include_dir / Path(self.fqname.replace('.', '/') + '.aidl'))

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
        for import_types in self.interface.imports:
            result.append(f"using ::{import_types.replace('.', '::')};")

        return "\n".join(result) + "\n"

    def _format_methods_definitions(self):
        result = []
        for method in self.interface.methods:
            args_formatted = ", ".join([arg.format() for arg in method.args])
            result.append(f"ndk::ScopedAStatus {self.class_name}::{method.name}({args_formatted}) {{\n"
                          f"    return ndk::ScopedAStatus::fromExceptionCode(EX_UNSUPPORTED_OPERATION);\n"
                          f"}}")

        return "\n\n".join(result)

    def _format_methods_declarations(self):
        result = []
        for method in self.interface.methods:
            args_formatted = ", ".join([arg.format() for arg in method.args])
            result.append(f"    ndk::ScopedAStatus {method.name}({args_formatted}) override;")

        return "\n".join(result)

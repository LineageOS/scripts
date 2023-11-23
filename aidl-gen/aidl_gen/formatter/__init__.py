#
# Copyright (C) 2023 The LineageOS Project
#
# SPDX-License-Identifier: Apache-2.0
#

from aidl_gen.aidl.method import Method

LICENSE_HEADER_TEMPLATE = \
"""\
{comment_start}
{comment_middle} Copyright (C) {year} The LineageOS Project
{comment_middle}
{comment_middle} SPDX-License-Identifier: Apache-2.0
{comment_end}
"""

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
        "libbase",
        "libbinder_ndk",
        "{aidl_name}-ndk",
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
        <version>{interface_version}</version>
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

{using_namespaces}

namespace aidl {{
{aidl_namespace_open}

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
#include <android-base/logging.h>

using ::aidl::{aidl_namespace}::{class_name};

int main() {{
    ABinderProcess_setThreadPoolMaxThreadCount(0);
    std::shared_ptr<{class_name}> {class_name_lower} = ndk::SharedRefBase::make<{class_name}>();

    const std::string instance = std::string() + {class_name}::descriptor + "/default";
    binder_status_t status = AServiceManager_addService({class_name_lower}->asBinder().get(), instance.c_str());
    CHECK(status == STATUS_OK);

    ABinderProcess_joinThreadPool();
    return EXIT_FAILURE;  // should not reach
}}
"""

class Formatter:
    @staticmethod
    def format_method(method: Method) -> str:
        raise NotImplementedError()

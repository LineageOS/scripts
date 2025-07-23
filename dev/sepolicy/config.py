# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

# Variables extracted from system/sepolicy/build/soong/policy.go

from __future__ import annotations

default_variables = {
    # MlsSens = 1
    'mls_num_sens': '1',
    # MlsCats = 1024
    'mls_num_cats': '1024',
    # TARGET_ARCH
    'target_arch': 'arm64',
    'target_with_asan': 'false',
    # WITH_DEXPREOPT
    'target_with_dexpreopt': 'false',
    'target_with_native_coverage': 'false',
    # TARGET_BUILD_VARIANT
    'target_build_variant': 'user',
    # expanded in compatible_property_only() and not_compatible_property()
    # not used in te_macros
    # set to false for recovery, cts for cts, true for anything else
    'target_compatible_property': 'true',
    # BUILD_BROKEN_ENFORCE_SYSPROP_OWNER
    # expanded in enforce_sysprop_owner()
    # not used in te_macros
    'target_enforce_sysprop_owner': 'true',
    # exclude_build_test property of the se_policy_conf Android.bp rule
    # only set for CTS
    'target_exclude_build_test': 'false',
    # PRODUCT_SET_DEBUGFS_RESTRICTIONS
    # expanded in enforce_debugfs_restriction() and no_debugfs_restriction()
    # not used in te_macros
    'target_enforce_debugfs_restriction': 'true',
    'target_recovery': 'false',
    # BOARD_API_LEVEL
    'target_board_api_level': '202404',
}

default_variables_choices = {
    # expanded in full_treble_only() and not_full_treble()
    'target_full_treble': ('true', 'false'),
    # BUILD_BROKEN_TREBLE_SYSPROP_NEVERALLOW
    'target_treble_sysprop_neverallow': ('true', 'false'),
}

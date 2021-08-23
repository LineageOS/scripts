/*
 * Copyright (C) 2021 The LineageOS Project
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "Power.h"

namespace aidl {
namespace android {
namespace hardware {
namespace power {

ndk::ScopedAStatus Power::setMode(Mode /*type*/, bool /*enabled*/) {
    return ndk::ScopedAStatus::fromExceptionCode(EX_UNSUPPORTED_OPERATION);
}

ndk::ScopedAStatus Power::isModeSupported(Mode /*type*/, bool* /*_aidl_return*/) {
    return ndk::ScopedAStatus::fromExceptionCode(EX_UNSUPPORTED_OPERATION);
}

ndk::ScopedAStatus Power::setBoost(Boost /*type*/, int32_t /*durationMs*/) {
    return ndk::ScopedAStatus::fromExceptionCode(EX_UNSUPPORTED_OPERATION);
}

ndk::ScopedAStatus Power::isBoostSupported(Boost /*type*/, bool* /*_aidl_return*/) {
    return ndk::ScopedAStatus::fromExceptionCode(EX_UNSUPPORTED_OPERATION);
}

} // namespace power
} // namespace hardware
} // namespace android
} // namespace aidl

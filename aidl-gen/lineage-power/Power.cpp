/*
 * Copyright (C) 2021 The LineageOS Project
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include "Power.h"

namespace aidl {
namespace vendor {
namespace lineage {
namespace power {

ndk::ScopedAStatus Power::getFeature(Feature feature, int32_t* _aidl_return) {
    return ndk::ScopedAStatus::fromExceptionCode(EX_UNSUPPORTED_OPERATION);
}

ndk::ScopedAStatus Power::setBoost(Boost type, int32_t durationMs) {
    return ndk::ScopedAStatus::fromExceptionCode(EX_UNSUPPORTED_OPERATION);
}

} // namespace power
} // namespace lineage
} // namespace vendor
} // namespace aidl

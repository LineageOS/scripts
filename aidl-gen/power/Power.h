/*
 * Copyright (C) 2021 The LineageOS Project
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#pragma once

#include <aidl/android/hardware/power/BnPower.h>

using ::aidl::android::hardware::power::Boost;
using ::aidl::android::hardware::power::Mode;

namespace aidl {
namespace android {
namespace hardware {
namespace power {

class Power : public BnPower {
public:
    ndk::ScopedAStatus setMode(Mode type, bool enabled) override;
    ndk::ScopedAStatus isModeSupported(Mode type, bool* _aidl_return) override;
    ndk::ScopedAStatus setBoost(Boost type, int32_t durationMs) override;
    ndk::ScopedAStatus isBoostSupported(Boost type, bool* _aidl_return) override;
};

} // namespace power
} // namespace hardware
} // namespace android
} // namespace aidl

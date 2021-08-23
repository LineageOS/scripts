/*
 * Copyright (C) 2021 The LineageOS Project
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#pragma once

#include <aidl/android/hardware/light/BnLights.h>

namespace aidl {
namespace android {
namespace hardware {
namespace light {

using ::android::hardware::light::HwLightState;
using ::android::hardware::light::HwLight;

class Lights : public BnLights {
public:
    ndk::ScopedAStatus setLightState(int32_t id, HwLightState state) override;
    ndk::ScopedAStatus getLights(std::vector<HwLight>* _aidl_return) override;
};

} // namespace light
} // namespace hardware
} // namespace android
} // namespace aidl

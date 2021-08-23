/*
 * Copyright (C) 2021 The LineageOS Project
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#pragma once

#include <aidl/vendor/lineage/power/BnPower.h>

namespace aidl {
namespace vendor {
namespace lineage {
namespace power {

using ::vendor::lineage::power::Boost;
using ::vendor::lineage::power::Feature;

class Power : public BnPower {
public:
    ndk::ScopedAStatus getFeature(Feature feature, int32_t* _aidl_return) override;
    ndk::ScopedAStatus setBoost(Boost type, int32_t durationMs) override;
};

} // namespace power
} // namespace lineage
} // namespace vendor
} // namespace aidl

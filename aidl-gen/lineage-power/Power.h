/*
 * Copyright (C) 2021 The LineageOS Project
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#pragma once

#include <aidl/vendor/lineage/power/BnPower.h>

using ::aidl::vendor::lineage::power::Boost;
using ::aidl::vendor::lineage::power::Feature;

namespace aidl {
namespace vendor {
namespace lineage {
namespace power {

class Power : public BnPower {
public:
    ndk::ScopedAStatus getFeature(Feature feature, int32_t* _aidl_return) override;
    ndk::ScopedAStatus setBoost(Boost type, int32_t durationMs) override;
};

} // namespace power
} // namespace lineage
} // namespace vendor
} // namespace aidl

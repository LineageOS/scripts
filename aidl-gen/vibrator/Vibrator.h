/*
 * Copyright (C) 2021 The LineageOS Project
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#pragma once

#include <aidl/android/hardware/vibrator/BnVibrator.h>

namespace aidl {
namespace android {
namespace hardware {
namespace vibrator {

using ::android::hardware::vibrator::IVibratorCallback;
using ::android::hardware::vibrator::Effect;
using ::android::hardware::vibrator::EffectStrength;
using ::android::hardware::vibrator::CompositeEffect;
using ::android::hardware::vibrator::CompositePrimitive;

class Vibrator : public BnVibrator {
public:
    ndk::ScopedAStatus getCapabilities(int32_t* _aidl_return) override;
    ndk::ScopedAStatus off() override;
    ndk::ScopedAStatus on(int32_t timeoutMs, IVibratorCallback callback) override;
    ndk::ScopedAStatus perform(Effect effect, EffectStrength strength, IVibratorCallback callback, int32_t* _aidl_return) override;
    ndk::ScopedAStatus getSupportedEffects(std::vector<Effect>* _aidl_return) override;
    ndk::ScopedAStatus setAmplitude(float amplitude) override;
    ndk::ScopedAStatus setExternalControl(bool enabled) override;
    ndk::ScopedAStatus getCompositionDelayMax(int32_t* _aidl_return) override;
    ndk::ScopedAStatus getCompositionSizeMax(int32_t* _aidl_return) override;
    ndk::ScopedAStatus getSupportedPrimitives(std::vector<CompositePrimitive>* _aidl_return) override;
    ndk::ScopedAStatus getPrimitiveDuration(CompositePrimitive primitive, int32_t* _aidl_return) override;
    ndk::ScopedAStatus compose(std::vector<CompositeEffect> composite, IVibratorCallback callback) override;
    ndk::ScopedAStatus getSupportedAlwaysOnEffects(std::vector<Effect>* _aidl_return) override;
    ndk::ScopedAStatus alwaysOnEnable(int32_t id, Effect effect, EffectStrength strength) override;
    ndk::ScopedAStatus alwaysOnDisable(int32_t id) override;
};

} // namespace vibrator
} // namespace hardware
} // namespace android
} // namespace aidl

# SPDX-FileCopyrightText: 2024-2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

PRODUCT_CERTIFICATE_OVERRIDES := \
    com.android.adbd:com.android.adbd.certificate.override \
    com.android.adservices:com.android.adservices.certificate.override \
    com.android.adservices.api:com.android.adservices.api.certificate.override \
    com.android.appsearch:com.android.appsearch.certificate.override \
    com.android.appsearch.apk:com.android.appsearch.apk.certificate.override \
    com.android.art:com.android.art.certificate.override \
    com.android.bluetooth:com.android.bluetooth.certificate.override \
    com.android.bt:com.android.bt.certificate.override \
    com.android.btservices:com.android.btservices.certificate.override \
    com.android.cellbroadcast:com.android.cellbroadcast.certificate.override \
    com.android.compos:com.android.compos.certificate.override \
    com.android.configinfrastructure:com.android.configinfrastructure.certificate.override \
    com.android.connectivity.resources:com.android.connectivity.resources.certificate.override \
    com.android.conscrypt:com.android.conscrypt.certificate.override \
    com.android.crashrecovery:com.android.crashrecovery.certificate.override \
    com.android.devicelock:com.android.devicelock.certificate.override \
    com.android.extservices:com.android.extservices.certificate.override \
    com.android.hardware.authsecret:com.android.hardware.authsecret.certificate.override \
    com.android.hardware.biometrics.face.virtual:com.android.hardware.biometrics.face.virtual.override \
    com.android.hardware.biometrics.fingerprint.virtual:com.android.hardware.biometrics.fingerprint.virtual.override \
    com.android.hardware.boot:com.android.hardware.boot.certificate.override \
    com.android.hardware.cas:com.android.hardware.cas.override \
    com.android.hardware.contexthub:com.android.hardware.contexthub.certificate.override \
    com.android.hardware.dumpstate:com.android.hardware.dumpstate.certificate.override \
    com.android.hardware.gatekeeper.nonsecure:com.android.hardware.gatekeeper.nonsecure.certificate.override \
    com.android.hardware.neuralnetworks:com.android.hardware.neuralnetworks.certificate.override \
    com.android.hardware.power:com.android.hardware.power.certificate.override \
    com.android.hardware.rebootescrow:com.android.hardware.rebootescrow.certificate.override \
    com.android.hardware.thermal:com.android.hardware.thermal.certificate.override \
    com.android.hardware.threadnetwork:com.android.hardware.threadnetwork.override \
    com.android.hardware.uwb:com.android.hardware.uwb.certificate.override \
    com.android.hardware.vibrator:com.android.hardware.vibrator.certificate.override \
    com.android.hardware.wifi:com.android.hardware.wifi.certificate.override \
    com.android.healthfitness:com.android.healthfitness.certificate.override \
    com.android.hotspot2.osulogin:com.android.hotspot2.osulogin.certificate.override \
    com.android.i18n:com.android.i18n.certificate.override \
    com.android.ipsec:com.android.ipsec.certificate.override \
    com.android.media:com.android.media.certificate.override \
    com.android.media.swcodec:com.android.media.swcodec.certificate.override \
    com.android.mediaprovider:com.android.mediaprovider.certificate.override \
    com.android.nearby.halfsheet:com.android.nearby.halfsheet.certificate.override \
    com.android.networkstack.tethering:com.android.networkstack.tethering.certificate.override \
    com.android.neuralnetworks:com.android.neuralnetworks.certificate.override \
    com.android.nfcservices:com.android.nfcservices.certificate.override \
    com.android.ondevicepersonalization:com.android.ondevicepersonalization.certificate.override \
    com.android.os.statsd:com.android.os.statsd.certificate.override \
    com.android.permission:com.android.permission.certificate.override \
    com.android.profiling:com.android.profiling.certificate.override \
    com.android.resolv:com.android.resolv.certificate.override \
    com.android.rkpd:com.android.rkpd.certificate.override \
    com.android.runtime:com.android.runtime.certificate.override \
    com.android.safetycenter.resources:com.android.safetycenter.resources.certificate.override \
    com.android.scheduling:com.android.scheduling.certificate.override \
    com.android.sdkext:com.android.sdkext.certificate.override \
    com.android.support.apexer:com.android.support.apexer.certificate.override \
    com.android.telephony:com.android.telephony.certificate.override \
    com.android.telephonycore:com.android.telephonycore.certificate.override \
    com.android.telephonymodules:com.android.telephonymodules.certificate.override \
    com.android.tethering:com.android.tethering.certificate.override \
    com.android.tzdata:com.android.tzdata.certificate.override \
    com.android.uprobestats:com.android.uprobestats.certificate.override \
    com.android.uwb:com.android.uwb.certificate.override \
    com.android.uwb.resources:com.android.uwb.resources.certificate.override \
    com.android.virt:com.android.virt.certificate.override \
    com.android.vndk.current:com.android.vndk.current.certificate.override \
    com.android.wifi:com.android.wifi.certificate.override \
    com.android.wifi.dialog:com.android.wifi.dialog.certificate.override \
    com.android.wifi.resources:com.android.wifi.resources.certificate.override \
    com.google.pixel.vibrator.hal:com.google.pixel.vibrator.hal.certificate.override \
    com.qorvo.uwb:com.qorvo.uwb.certificate.override

PRODUCT_CERTIFICATE_OVERRIDES += \
    AdServicesApk:com.android.adservices.api.certificate.override \
    FederatedCompute:com.android.federatedcompute.certificate.override \
    HealthConnectBackupRestore:com.android.health.connect.backuprestore.certificate.override \
    HealthConnectController:com.android.healthconnect.controller.certificate.override \
    OsuLogin:com.android.hotspot2.osulogin.certificate.override \
    SafetyCenterResources:com.android.safetycenter.resources.certificate.override \
    ServiceConnectivityResources:com.android.connectivity.resources.certificate.override \
    ServiceUwbResources:com.android.uwb.resources.certificate.override \
    ServiceWifiResources:com.android.wifi.resources.certificate.override \
    WifiDialog:com.android.wifi.dialog.certificate.override

PRODUCT_DEFAULT_DEV_CERTIFICATE := vendor/lineage-priv/keys/testkey
PRODUCT_EXTRA_RECOVERY_KEYS :=

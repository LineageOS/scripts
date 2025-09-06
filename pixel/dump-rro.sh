#!/bin/bash

# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-FileCopyrightText: The Calyx Institute
# SPDX-License-Identifier: Apache-2.0

#
# dev:
#
#   Extract various things from stock factory images for development purposes
#
#
##############################################################################


### SET ###

# use bash strict mode
set -euo pipefail

### TRAPS ###

# trap signals for clean exit
trap 'exit $?' EXIT
trap 'error_m interrupted!' SIGINT

### CONSTANTS ###
readonly script_path="$(cd "$(dirname "$0")";pwd -P)"
readonly vars_path="${script_path}/../../../vendor/lineage/vars"
readonly top="${script_path}/../../.."

readonly work_dir="${WORK_DIR:-/tmp/pixel}"

source "${vars_path}/pixels"
source "${vars_path}/common"

export vars_path work_dir build_id image_sha256 image_url

## HELP MESSAGE (USAGE INFO)
# TODO

### FUNCTIONS ###

declare -a exclude_overlay_names=(
  com.android.bips.auto_generated_rro_product__
  com.android.captiveportallogin.overlay
  com.android.cellbroadcastreceiver.overlay.pixel
  com.android.cellbroadcastservice.overlay.pixel
  com.android.healthconnect.overlay
  com.android.managedprovisioning.overlay
  com.android.providers.contacts.auto_generated_rro_product__
  com.android.providers.media.overlay.pixel
  com.android.simappdialog.auto_generated_rro_product__
  com.android.systemui.accessibility.accessibilitymenu.auto_generated_rro_product__
  com.android.systemui.overlay.spoonoverlay2025
  com.google.android.documentsui.theme.pixel
  com.google.android.pixel.avatarpicker
  com.google.android.overlay.devicelockcontroller
  com.google.android.overlay.googlewebview
  com.google.android.overlay.permissioncontroller
  com.google.android.overlay.trafficlightfaceoverlay
  com.google.android.overlay.udfpsoverlay
  com.google.android.settings.overlay.pixelvpnconfig
  com.google.android.systemui.gxoverlay
  com.google.android.verifier.overlay
)

declare -a keep_package_names=(
  com.android.hbmsvmanager
  com.android.omadm.service
  com.android.pixeldisplayservice
  com.google.android.apps.scone
  com.google.android.docksetup
  com.google.android.grilservice
  com.google.euiccpixel
  com.shannon.imsservice
)

declare -a keep_resource_names=(
  "com.android.settings:regulatory_info_*"
)

declare -a prefer_resource_names=(
  android.overlay.product.comet:config_fixedOrientationLetterboxAspectRatio
  android.overlay.product.comet:config_letterboxIsEducationEnabled
  android.overlay.product.comet:config_letterboxIsSplitScreenAspectRatioForUnresizableAppsEnabled
  android.overlay.product.comet:config_showUserSwitcherByDefault
  android.overlay.product.felix:config_showUserSwitcherByDefault
  android.overlay.product.rango:config_fixedOrientationLetterboxAspectRatio
  android.overlay.product.rango:config_letterboxActivityCornersRadius
  android.overlay.product.rango:config_letterboxIsEducationEnabled
  android.overlay.product.rango:config_letterboxIsSplitScreenAspectRatioForUnresizableAppsEnabled
  android.overlay.product.rango:config_showUserSwitcherByDefault
  com.google.android.overlay.pixelconfigcommon:config_fingerprintSupportsGestures
  com.google.android.overlay.titansettings:screensaver_settings_summary_postured_and_charging
  com.google.android.overlay.titansettings:screensaver_settings_summary_sleep
  com.google.android.overlay.titansettings:when_to_show_hubmode_charging
  com.google.android.overlay.titansettings:when_to_show_hubmode_docked
  com.google.android.overlay.titansettings:when_to_show_hubmode_never
  com.google.android.overlay.titansettings:when_to_start_hubmode_entries
  com.google.android.overlay.titansettings:when_to_start_hubmode_values
  com.google.android.overlay.titansettings:when_to_start_screensaver_entries_no_battery
  com.google.android.overlay.titansettings:when_to_start_screensaver_values_no_battery
  com.google.android.overlay.titansettings:config_show_restrict_to_wireless_charging
  com.google.android.overlay.titansettingsprovider:def_screen_off_timeout
  com.google.android.systemui.overlay.titanconfig:config_communalWidgetAllowlist
  com.google.android.systemui.overlay.titanconfig:config_swipeToOpenGlanceableHub
  com.google.android.wifi.resources.pixel.laguna:config_wifi11axSupportOverride
  com.google.android.wifi.resources.pixel.laguna:config_wifi5ghzSupport
  com.google.android.wifi.resources.pixel.laguna:config_wifi6ghzSupport
  com.google.android.wifi.resources.pixel.laguna:config_wifiAdjustPollRssiIntervalEnabled
  com.google.android.wifi.resources.pixel.laguna:config_wifiAllowNonPersistentMacRandomizationOnOpenSsids
  com.google.android.wifi.resources.pixel.laguna:config_wifiBridgedSoftApSupported
  com.google.android.wifi.resources.pixel.laguna:config_wifiChannelUtilizationOverrideEnabled
  com.google.android.wifi.resources.pixel.laguna:config_wifiCoexForGpsL1
  com.google.android.wifi.resources.pixel.laguna:config_wifiCoexGpsL1ThresholdKhz
  com.google.android.wifi.resources.pixel.laguna:config_wifiDefaultCoexAlgorithmEnabled
  com.google.android.wifi.resources.pixel.laguna:config_wifiDisableFirmwareRoamingInIdleMode
  com.google.android.wifi.resources.pixel.laguna:config_wifiDriverSupportedNl80211RegChangedEvent
  com.google.android.wifi.resources.pixel.laguna:config_wifiDtimMultiplierConfigEnabled
  com.google.android.wifi.resources.pixel.laguna:config_wifiEnablePartialInitialScan
  com.google.android.wifi.resources.pixel.laguna:config_wifiEnableStaDfsChannelForPeerNetwork
  com.google.android.wifi.resources.pixel.laguna:config_wifiEnableStaIndoorChannelForPeerNetwork
  com.google.android.wifi.resources.pixel.laguna:config_wifiFrameworkSoftApDisableBridgedModeShutdownIdleInstanceWhenCharging
  com.google.android.wifi.resources.pixel.laguna:config_wifiHardwareSoftapMaxClientCount
  com.google.android.wifi.resources.pixel.laguna:config_wifiInitialPartialScanMaxNewChannelsPerNetwork
  com.google.android.wifi.resources.pixel.laguna:config_wifiLinkLayerAllRadiosStatsAggregationEnabled
  com.google.android.wifi.resources.pixel.laguna:config_wifiMainlineSupplicantEnabled
  com.google.android.wifi.resources.pixel.laguna:config_wifiMaxNativeFailureSelfRecoveryPerHour
  com.google.android.wifi.resources.pixel.laguna:config_wifiMinConfirmationDurationSendNetworkScoreEnabled
  com.google.android.wifi.resources.pixel.laguna:config_wifiMultiStaLocalOnlyConcurrencyEnabled
  com.google.android.wifi.resources.pixel.laguna:config_wifiMultiStaNetworkSwitchingMakeBeforeBreakEnabled
  com.google.android.wifi.resources.pixel.laguna:config_wifiRssiLevelThresholds
  com.google.android.wifi.resources.pixel.laguna:config_wifiSaeH2eSupported
  com.google.android.wifi.resources.pixel.laguna:config_wifiSaeUpgradeEnabled
  com.google.android.wifi.resources.pixel.laguna:config_wifiSaeUpgradeOffloadEnabled
  com.google.android.wifi.resources.pixel.laguna:config_wifiSoftap6ghzSupported
  com.google.android.wifi.resources.pixel.laguna:config_wifiSoftapIeee80211axSupported
  com.google.android.wifi.resources.pixel.laguna:config_wifiStaWithBridgedSoftApConcurrencySupported
  com.google.android.wifi.resources.pixel.laguna:config_wifiTwtSupported
  com.google.android.wifi.resources.pixel.laguna:config_wifiUpdateCountryCodeFromScanResultGeneric
  com.google.android.wifi.resources.pixel.laguna:config_wifiUpdateCountryCodeFromScanResultSetupWizard
  com.google.android.wifi.resources.pixel.laguna:config_wifiUseHalApiToDisableFwRoaming
  com.google.android.wifi.resources.pixel.laguna:config_wifiVerboseLoggingAlwaysOnLevel
  com.google.android.wifi.resources.pixel.laguna:config_wifiWaitForDestroyedListeners
  com.google.android.wifi.resources.pixel.laguna:config_wifi_ap_mac_randomization_supported
  com.google.android.wifi.resources.pixel.laguna:config_wifi_background_scan_support
  com.google.android.wifi.resources.pixel.laguna:config_wifi_connected_mac_randomization_supported
  com.google.android.wifi.resources.pixel.laguna:config_wifi_diagnostics_bugreport_enabled
  com.google.android.wifi.resources.pixel.laguna:config_wifi_fast_bss_transition_enabled
  com.google.android.wifi.resources.pixel.laguna:config_wifi_fatal_firmware_alert_error_code_list
  com.google.android.wifi.resources.pixel.laguna:config_wifi_framework_recovery_timeout_delay
  com.google.android.wifi.resources.pixel.laguna:config_wifi_framework_wifi_score_bad_rssi_threshold_24GHz
  com.google.android.wifi.resources.pixel.laguna:config_wifi_framework_wifi_score_bad_rssi_threshold_5GHz
  com.google.android.wifi.resources.pixel.laguna:config_wifi_framework_wifi_score_entry_rssi_threshold_24GHz
  com.google.android.wifi.resources.pixel.laguna:config_wifi_framework_wifi_score_entry_rssi_threshold_5GHz
  com.google.android.wifi.resources.pixel.laguna:config_wifi_link_probing_supported
  com.google.android.wifi.resources.pixel.laguna:config_wifi_p2p_mac_randomization_supported
  com.google.android.wifi.resources.pixel.laguna:config_wifi_revert_country_code_on_cellular_loss
  com.google.android.wifi.resources.pixel.laguna:config_wifi_softap_acs_supported
  com.google.android.wifi.resources.pixel.laguna:config_wifi_softap_ieee80211ac_supported
  com.google.android.wifi.resources.pixel.laguna:config_wifi_softap_sae_supported
  com.google.android.wifi.resources.pixel.laguna:config_wifi_subsystem_restart_bugreport_enabled
  com.google.android.wifi.resources.pixel.laguna:config_wifi_tcp_buffers
  com.google.android.wifi.resources.pixel.laguna:config_wifi_turn_off_during_emergency_call
  com.google.android.wifi.resources.pixel.laguna:wifi_tether_configure_ssid_default
  com.google.android.wifi.resources.pixel.zumapro:config_wifi11axSupportOverride
  com.google.android.wifi.resources.pixel.zumapro:config_wifi5ghzSupport
  com.google.android.wifi.resources.pixel.zumapro:config_wifi6ghzSupport
  com.google.android.wifi.resources.pixel.zumapro:config_wifiAdjustPollRssiIntervalEnabled
  com.google.android.wifi.resources.pixel.zumapro:config_wifiAllowNonPersistentMacRandomizationOnOpenSsids
  com.google.android.wifi.resources.pixel.zumapro:config_wifiBridgedSoftApSupported
  com.google.android.wifi.resources.pixel.zumapro:config_wifiChannelUtilizationOverrideEnabled
  com.google.android.wifi.resources.pixel.zumapro:config_wifiCoexForGpsL1
  com.google.android.wifi.resources.pixel.zumapro:config_wifiCoexGpsL1ThresholdKhz
  com.google.android.wifi.resources.pixel.zumapro:config_wifiDefaultCoexAlgorithmEnabled
  com.google.android.wifi.resources.pixel.zumapro:config_wifiDisableFirmwareRoamingInIdleMode
  com.google.android.wifi.resources.pixel.zumapro:config_wifiDriverSupportedNl80211RegChangedEvent
  com.google.android.wifi.resources.pixel.zumapro:config_wifiDtimMultiplierConfigEnabled
  com.google.android.wifi.resources.pixel.zumapro:config_wifiEnablePartialInitialScan
  com.google.android.wifi.resources.pixel.zumapro:config_wifiEnableStaDfsChannelForPeerNetwork
  com.google.android.wifi.resources.pixel.zumapro:config_wifiEnableStaIndoorChannelForPeerNetwork
  com.google.android.wifi.resources.pixel.zumapro:config_wifiFrameworkSoftApDisableBridgedModeShutdownIdleInstanceWhenCharging
  com.google.android.wifi.resources.pixel.zumapro:config_wifiHardwareSoftapMaxClientCount
  com.google.android.wifi.resources.pixel.zumapro:config_wifiInitialPartialScanMaxNewChannelsPerNetwork
  com.google.android.wifi.resources.pixel.zumapro:config_wifiLinkLayerAllRadiosStatsAggregationEnabled
  com.google.android.wifi.resources.pixel.zumapro:config_wifiMainlineSupplicantEnabled
  com.google.android.wifi.resources.pixel.zumapro:config_wifiMaxNativeFailureSelfRecoveryPerHour
  com.google.android.wifi.resources.pixel.zumapro:config_wifiMinConfirmationDurationSendNetworkScoreEnabled
  com.google.android.wifi.resources.pixel.zumapro:config_wifiMultiStaLocalOnlyConcurrencyEnabled
  com.google.android.wifi.resources.pixel.zumapro:config_wifiMultiStaNetworkSwitchingMakeBeforeBreakEnabled
  com.google.android.wifi.resources.pixel.zumapro:config_wifiRssiLevelThresholds
  com.google.android.wifi.resources.pixel.zumapro:config_wifiSaeH2eSupported
  com.google.android.wifi.resources.pixel.zumapro:config_wifiSaeUpgradeEnabled
  com.google.android.wifi.resources.pixel.zumapro:config_wifiSaeUpgradeOffloadEnabled
  com.google.android.wifi.resources.pixel.zumapro:config_wifiSoftap6ghzSupported
  com.google.android.wifi.resources.pixel.zumapro:config_wifiSoftapIeee80211axSupported
  com.google.android.wifi.resources.pixel.zumapro:config_wifiStaWithBridgedSoftApConcurrencySupported
  com.google.android.wifi.resources.pixel.zumapro:config_wifiTwtSupported
  com.google.android.wifi.resources.pixel.zumapro:config_wifiUpdateCountryCodeFromScanResultGeneric
  com.google.android.wifi.resources.pixel.zumapro:config_wifiUpdateCountryCodeFromScanResultSetupWizard
  com.google.android.wifi.resources.pixel.zumapro:config_wifiUseHalApiToDisableFwRoaming
  com.google.android.wifi.resources.pixel.zumapro:config_wifiVerboseLoggingAlwaysOnLevel
  com.google.android.wifi.resources.pixel.zumapro:config_wifiWaitForDestroyedListeners
  com.google.android.wifi.resources.pixel.zumapro:config_wifi_ap_mac_randomization_supported
  com.google.android.wifi.resources.pixel.zumapro:config_wifi_background_scan_support
  com.google.android.wifi.resources.pixel.zumapro:config_wifi_connected_mac_randomization_supported
  com.google.android.wifi.resources.pixel.zumapro:config_wifi_diagnostics_bugreport_enabled
  com.google.android.wifi.resources.pixel.zumapro:config_wifi_fast_bss_transition_enabled
  com.google.android.wifi.resources.pixel.zumapro:config_wifi_fatal_firmware_alert_error_code_list
  com.google.android.wifi.resources.pixel.zumapro:config_wifi_framework_recovery_timeout_delay
  com.google.android.wifi.resources.pixel.zumapro:config_wifi_framework_wifi_score_bad_rssi_threshold_24GHz
  com.google.android.wifi.resources.pixel.zumapro:config_wifi_framework_wifi_score_bad_rssi_threshold_5GHz
  com.google.android.wifi.resources.pixel.zumapro:config_wifi_framework_wifi_score_entry_rssi_threshold_24GHz
  com.google.android.wifi.resources.pixel.zumapro:config_wifi_framework_wifi_score_entry_rssi_threshold_5GHz
  com.google.android.wifi.resources.pixel.zumapro:config_wifi_link_probing_supported
  com.google.android.wifi.resources.pixel.zumapro:config_wifi_p2p_mac_randomization_supported
  com.google.android.wifi.resources.pixel.zumapro:config_wifi_revert_country_code_on_cellular_loss
  com.google.android.wifi.resources.pixel.zumapro:config_wifi_softap_acs_supported
  com.google.android.wifi.resources.pixel.zumapro:config_wifi_softap_ieee80211ac_supported
  com.google.android.wifi.resources.pixel.zumapro:config_wifi_softap_sae_supported
  com.google.android.wifi.resources.pixel.zumapro:config_wifi_subsystem_restart_bugreport_enabled
  com.google.android.wifi.resources.pixel.zumapro:config_wifi_tcp_buffers
  com.google.android.wifi.resources.pixel.zumapro:config_wifi_turn_off_during_emergency_call
  com.google.android.wifi.resources.pixel.zumapro:wifi_tether_configure_ssid_default
)

declare -a remove_resource_names=(
  android:android_start_title
  android:android_upgrading_title
  android:battery_saver_description_with_learn_more
  android:biometric_app_setting_name
  android:biometric_dialog_default_subtitle
  android:biometric_or_screen_lock_app_setting_name
  android:biometric_or_screen_lock_dialog_default_subtitle
  android:bookmarks.xml
  android:config_accessComputerControlKnownSigners
  android:config_allowedSecureInstantAppSettings
  android:config_ambientContextEventArrayExtraKey
  android:config_ambientContextPackageNameExtraKey
  android:config_appFunctionDeviceSettingsPackages
  android:config_appsAuthorizedForSharedAccounts
  android:config_assistLongPressHomeEnabledDefault
  android:config_assistTouchGestureEnabledDefault
  android:config_backupHealthConnectDataAndSettingsKnownSigners
  android:config_batteryPackageTypeService
  android:config_biometricFrrNotificationEnabled
  android:config_biometricNotificationFrrThreshold
  android:config_bodyFontFamily
  android:config_bodyFontFamilyMedium
  android:config_bugReportHandlerEnabled
  android:config_buttonTextAllCaps
  android:config_clockFontFamily
  android:config_companionDeviceCerts
  android:config_companionDevicePackages
  android:config_defaultAccessibilityNotificationSound
  android:config_defaultAccessibilityService
  android:config_defaultAmbientContextConsentComponent
  android:config_defaultAmbientContextDetectionService
  android:config_defaultAppFunctionAgentAllowlist
  android:config_defaultAssistant
  android:config_defaultAssistantAccessComponent
  android:config_defaultAugmentedAutofillService
  android:config_defaultAutofillService
  android:config_defaultBugReportHandlerApp
  android:config_defaultCaptivePortalLoginPackageName
  android:config_defaultCloudSearchServices
  android:config_defaultContentCaptureService
  android:config_defaultContentProtectionService
  android:config_defaultContextualSearchEnabled
  android:config_defaultContextualSearchKey
  android:config_defaultContextualSearchLegacyEnabled
  android:config_defaultContextualSearchPackageName
  android:config_defaultCredentialManagerHybridService
  android:config_defaultDialer
  android:config_defaultDndAccessPackages
  android:config_defaultDockManagerPackageName
  android:config_defaultFieldClassificationService
  android:config_defaultFirstUserRestrictions
  android:config_defaultListenerAccessPackages
  android:config_defaultModuleMetadataProvider
  android:config_defaultMusicRecognitionService
  android:config_defaultNearbyFastPairSettingsDevicesComponent
  android:config_defaultNearbySharingComponent
  android:config_defaultNetworkRecommendationProviderPackage
  android:config_defaultNightMode
  android:config_defaultOnDeviceIntelligenceDeviceConfigNamespace
  android:config_defaultOnDeviceIntelligenceService
  android:config_defaultOnDeviceSandboxedInferenceService
  android:config_defaultOnDeviceSpeechRecognitionService
  android:config_defaultProfcollectReportUploaderAction
  android:config_defaultProfcollectReportUploaderApp
  android:config_defaultQrCodeComponent
  android:config_defaultRetailDemo
  android:config_defaultRingtonePickerEnabled
  android:config_defaultSearchSelectorPackageName
  android:config_defaultSearchUiService
  android:config_defaultSelectToSpeakService
  android:config_defaultSmartspaceService
  android:config_defaultSms
  android:config_defaultSupervisionProfileOwnerComponent
  android:config_defaultTextClassifierPackage
  android:config_defaultTranslationService
  android:config_defaultVoiceAccessService
  android:config_defaultWallet
  android:config_defaultWallpaperEffectsGenerationService
  android:config_defaultWellbeingPackage
  android:config_deviceConfiguratorPackageName
  android:config_devicePolicyManagement
  android:config_devicePolicyManagementUpdater
  android:config_deviceProvisioningPackage
  android:config_disabledUntilUsedPreinstalledImes
  android:config_doubleTapPowerGestureMode
  android:config_dreamsDefaultComponent
  android:config_emergency_dialer_package
  android:config_enablePrimaryLocationTimeZoneProvider
  android:config_enabledCredentialProviderService
  android:config_ephemeralResolverPackage
  android:config_faceAuthDismissesKeyguard
  android:config_face_acquire_biometricprompt_ignorelist
  android:config_face_acquire_enroll_ignorelist
  android:config_face_acquire_keyguard_ignorelist
  android:config_face_acquire_vendor_biometricprompt_ignorelist
  android:config_face_acquire_vendor_enroll_ignorelist
  android:config_face_acquire_vendor_keyguard_ignorelist
  android:config_feedbackIntentExtraKey
  android:config_feedbackIntentNameKey
  android:config_fingerprintFrrTargetComponent
  android:config_fontManagerServiceCerts
  android:config_forceQueryablePackages
  android:config_gnssLocationOverlayUnstableFallback
  android:config_gnssLocationProviderPackageName
  android:config_headlineFontFamily
  android:config_headlineFontFamilyMedium
  android:config_headlineFontFeatureSettings
  android:config_healthConnectMigrationKnownSigners
  android:config_healthConnectMigratorPackageName
  android:config_healthConnectRestoreKnownSigners
  android:config_helpIntentExtraKey
  android:config_helpIntentNameKey
  android:config_helpPackageNameKey
  android:config_helpPackageNameValue
  android:config_help_url_action_disabled_by_advanced_protection
  android:config_hideWhenDisabled_packageNames
  android:config_icon_mask
  android:config_incidentReportApproverPackage
  android:config_integrityRuleProviderPackages
  android:config_intrusionDetectionEventTransport
  android:config_keep_warming_services
  android:config_keyChordPowerVolumeUp
  android:config_locationExtraPackageNames
  android:config_locationProviderPackageNames
  android:config_loggable_dream_prefixes
  android:config_longPressOnHomeBehavior
  android:config_longPressOnPowerBehavior
  android:config_mobile_hotspot_provision_app
  android:config_mobile_hotspot_provision_app_no_ui
  android:config_mobile_hotspot_provision_response
  android:config_networkAvoidBadWifi
  android:config_notificationDefaultUnsupportedAdjustments
  android:config_notificationVibrationPatternToMetricIdMapping
  android:config_oemCredentialManagerDialogComponent
  android:config_packagesExemptFromSuspension
  android:config_persistentDataPackageName
  android:config_pinnerCameraApp
  android:config_powerSaveModeChangedListenerPackage
  android:config_preferredSystemImageEditor
  android:config_primaryCredentialProviderService
  android:config_primaryLocationTimeZoneProviderPackageName
  android:config_priorityOnlyDndExemptPackages
  android:config_profcollectOnCameraOpenedSkipPackages
  android:config_profcollectReportUploaderEnabled
  android:config_progress_background_tint.xml
  android:config_rawContactsEligibleDefaultAccountTypes
  android:config_recentsComponentName
  android:config_repairModeSupported
  android:config_restoreHealthConnectDataAndSettingsKnownSigners
  android:config_retailDemoPackage
  android:config_retailDemoPackageSignature
  android:config_ringtoneVibrationPatternToMetricIdMapping
  android:config_secondaryHomePackage
  android:config_sendPackageName
  android:config_servicesExtensionPackage
  android:config_setContactsDefaultAccountKnownSigners
  android:config_settingsHelpLinksEnabled
  android:config_sharedConnectivityServiceIntentAction
  android:config_sharedConnectivityServicePackage
  android:config_shortPressOnPowerBehavior
  android:config_showGesturalNavigationHints
  android:config_smart_battery_available
  android:config_storageManagerDaystoRetainDefault
  android:config_supportDoubleTapSleep
  android:config_supportLongPressPowerWhenNonInteractive
  android:config_supportsCamToggle
  android:config_supportsMicToggle
  android:config_systemActivityRecognizer
  android:config_systemAppProtectionService
  android:config_systemAutomotiveProjection
  android:config_systemBluetoothStack
  android:config_systemCallStreaming
  android:config_systemCaptionsServiceCallsEnabled
  android:config_systemCompanionDeviceProvider
  android:config_systemContacts
  android:config_systemDependencyInstaller
  android:config_systemFinancedDeviceController
  android:config_systemGallery
  android:config_systemGameService
  android:config_systemImageEditor
  android:config_systemSettingsIntelligence
  android:config_systemSpeechRecognizer
  android:config_systemSupervision
  android:config_systemWellbeing
  android:config_tether_usb_regexs
  android:config_tether_wifi_regexs
  android:config_trustedAccessibilityServices
  android:config_useGnssHardwareProvider
  android:config_useRoundIcon
  android:config_volumeHushGestureEnabled
  android:config_wallpaperCropperPackage
  android:default_wallpaper.png
  android:default_wallpaper_component
  android:error_color_device_default_dark
  android:error_color_device_default_light
  android:face_acquired_vendor
  android:face_error_vendor
  android:face_recalibrate_notification_content
  android:face_recalibrate_notification_name
  android:face_recalibrate_notification_title
  android:harmful_app_warning_title
  android:ic_doc_apk.xml
  android:ic_doc_audio.xml
  android:ic_doc_certificate.xml
  android:ic_doc_codes.xml
  android:ic_doc_compressed.xml
  android:ic_doc_contact.xml
  android:ic_doc_document.xml
  android:ic_doc_event.xml
  android:ic_doc_excel.xml
  android:ic_doc_folder.xml
  android:ic_doc_font.xml
  android:ic_doc_generic.xml
  android:ic_doc_image.xml
  android:ic_doc_pdf.xml
  android:ic_doc_powerpoint.xml
  android:ic_doc_presentation.xml
  android:ic_doc_spreadsheet.xml
  android:ic_doc_text.xml
  android:ic_doc_video.xml
  android:ic_doc_word.xml
  android:identity_check_settings_action
  android:identity_check_settings_package_name
  android:proximity_provider_service_class_name
  android:proximity_provider_service_package_name
  android:quick_qs_offset_height
  android:safety_protection_display_text
  android:scCellularNetworkSecurityLearnMore
  android:trusted_location_settings_action
  android:user_icon_1
  android:vendor_cross_profile_apps
  android:vendor_disallowed_apps_managed_device
  android:vendor_disallowed_apps_managed_profile
  android:vendor_disallowed_apps_managed_user
  android:vendor_required_apps_managed_device
  android:vendor_required_apps_managed_profile
  android:vendor_required_apps_managed_user
  android:vendor_required_attestation_certificates
  android:vendor_required_attestation_revocation_list_url
  android:widget_default_class_name
  android:widget_default_package_name
  com.android.connectivity.resources:config_activelyPreferBadWifi
  com.android.devicediagnostics:config_avatar_picker_package
  com.android.devicediagnostics:config_hspa_data_distinguishable
  com.android.devicediagnostics:config_showMin3G
  com.android.devicediagnostics:data_connection_5g_plus
  com.android.devicediagnostics:display_density_max_scale
  com.android.devicediagnostics:entryvalues_font_size
  com.android.devicediagnostics:ic_5g_plus_mobiledata.xml
  com.android.devicediagnostics:ic_5g_plus_mobiledata_updated.xml
  com.android.devicediagnostics:settingslib_learn_more_text
  com.android.networkstack.tethering:config_mobile_hotspot_provision_app
  com.android.networkstack.tethering:config_mobile_hotspot_provision_app_no_ui
  com.android.networkstack.tethering:config_mobile_hotspot_provision_response
  com.android.omadm.service:config_omadm_metrics_app_package
  com.android.omadm.service:config_omadm_metrics_class_name
  com.android.omadm.service:config_omadm_metrics_enabled
  com.android.omadm.service:config_omadm_metrics_extra_log_bytes
  com.android.omadm.service:config_omadm_metrics_extra_log_source
  com.android.omadm.service:config_omadm_metrics_intent_action
  com.android.phone:carrier_settings
  com.android.phone:carrier_settings_menu
  com.android.phone:config_apn_expand
  com.android.phone:config_carrier_settings_enable
  com.android.phone:config_show_cdma
  com.android.phone:config_use_hfa_for_provisioning
  com.android.phone:dialer_default_class
  com.android.phone:incall_error_promote_wfc
  com.android.phone:platform_number_verification_package
  com.android.phone:status_hint_label_incoming_wifi_call
  com.android.phone:status_hint_label_wifi_call
  com.android.phone:support_swap_after_merge
  com.android.phone:wifi_calling
  com.android.phone:wifi_calling_settings_title
  com.android.providers.settings:def_backup_transport
  com.android.providers.settings:def_double_tap_to_sleep
  com.android.providers.settings:def_screen_off_timeout
  com.android.providers.settings:def_vibrate_when_ringing
  com.android.providers.settings:def_wireless_charging_started_sound
  com.android.server.telecom:call_diagnostic_service_package_name
  com.android.server.telecom:dialer_default_class
  com.android.settings:config_avatar_picker_package
  com.android.settings:config_hspa_data_distinguishable
  com.android.settings:config_network_selection_list_aggregation_enabled
  com.android.settings:config_settings_slices_accessibility_components
  com.android.settings:config_showMin3G
  com.android.settings:config_suw_support_face_enroll
  com.android.settings:data_connection_5g_plus
  com.android.settings:display_white_balance_summary
  com.android.settings:display_white_balance_title
  com.android.settings:face_education.mp4
  com.android.settings:face_enroll_intro_illustration_margin_bottom
  com.android.settings:face_preview_scale
  com.android.settings:face_preview_translate_x
  com.android.settings:face_preview_translate_y
  com.android.settings:fingerprint_acquired_imager_dirty_udfps
  com.android.settings:fingerprint_location_animation.mp4
  com.android.settings:fingerprint_unlock_set_unlock_password
  com.android.settings:fingerprint_unlock_set_unlock_pattern
  com.android.settings:fingerprint_unlock_set_unlock_pin
  com.android.settings:fingerprint_unlock_skip_fingerprint
  com.android.settings:fingerprint_unlock_title
  com.android.settings:help_url_fingerprint
  com.android.settings:help_uri_private_dns
  com.android.settings:ic_5g_plus_mobiledata.xml
  com.android.settings:ic_5g_plus_mobiledata_updated.xml
  com.android.settings:icon_accent
  com.android.settings:link_locale_picker_footer_learn_more
  com.android.settings:location_settings_footer_learn_more_link
  com.android.settings:peak_refresh_rate_summary
  com.android.settings:regional_pref_footer_learn_more_link
  com.android.settings:security_settings_fingerprint_enroll_consent_introduction_title
  com.android.settings:security_settings_fingerprint_enroll_introduction_message_unlock_disabled
  com.android.settings:security_settings_fingerprint_enroll_introduction_title
  com.android.settings:security_settings_fingerprint_enroll_introduction_title_unlock_disabled
  com.android.settings:security_settings_fingerprint_preference_title
  com.android.settings:security_settings_fingerprint_v2_enroll_introduction_footer_message_6
  com.android.settings:security_settings_fingerprint_v2_enroll_introduction_message_learn_more
  com.android.settings:security_settings_udfps_enroll_fingertip_title
  com.android.settings:security_settings_udfps_enroll_left_edge_title
  com.android.settings:security_settings_udfps_enroll_right_edge_title
  com.android.settings:settingslib_learn_more_text
  com.android.settings:shortcut_base.png
  com.android.settings:slice_allowlist_package_names
  com.android.settings:slice_allowlist_package_names_for_dev
  com.android.settings:suggested_fingerprint_lock_settings_summary
  com.android.storagemanager:config_avatar_picker_package
  com.android.storagemanager:config_hspa_data_distinguishable
  com.android.storagemanager:config_showMin3G
  com.android.storagemanager:data_connection_5g_plus
  com.android.storagemanager:display_density_max_scale
  com.android.storagemanager:entryvalues_font_size
  com.android.storagemanager:ic_5g_plus_mobiledata.xml
  com.android.storagemanager:ic_5g_plus_mobiledata_updated.xml
  com.android.storagemanager:settingslib_learn_more_text
  com.android.systemui:ambientcue_first_time_edu_text
  com.android.systemui:config_avatar_picker_package
  com.android.systemui:config_controlsPreferredPackages
  com.android.systemui:config_face_auth_props
  com.android.systemui:config_hspa_data_distinguishable
  com.android.systemui:config_pluginAllowlist
  com.android.systemui:config_preferredScreenshotEditor
  com.android.systemui:config_remoteCopyPackage
  com.android.systemui:config_screenshotEditor
  com.android.systemui:config_screenshotFilesApp
  com.android.systemui:config_showMin3G
  com.android.systemui:data_connection_5g_plus
  com.android.systemui:ic_5g_plus_mobiledata.xml
  com.android.systemui:ic_5g_plus_mobiledata_updated.xml
  com.android.systemui:quick_settings_tiles_default
  com.android.systemui:quick_settings_tiles_new_default
  com.android.systemui:settingslib_learn_more_text
  com.android.systemui:stat_sys_branded_vpn.xml
  com.android.systemui:status_bar_header_height_keyguard
  com.android.systemui:status_bar_height
  com.android.traceur:config_avatar_picker_package
  com.android.traceur:config_hspa_data_distinguishable
  com.android.traceur:config_showMin3G
  com.android.traceur:data_connection_5g_plus
  com.android.traceur:display_density_max_scale
  com.android.traceur:entryvalues_font_size
  com.android.traceur:ic_5g_plus_mobiledata.xml
  com.android.traceur:ic_5g_plus_mobiledata_updated.xml
  com.android.traceur:settingslib_learn_more_text
  com.google.android.docksetup:config_avatar_picker_package
  com.google.android.docksetup:config_hspa_data_distinguishable
  com.google.android.docksetup:config_showMin3G
  com.google.android.docksetup:data_connection_5g_plus
  com.google.android.docksetup:display_density_max_scale
  com.google.android.docksetup:ic_5g_plus_mobiledata.xml
  com.google.android.docksetup:ic_5g_plus_mobiledata_updated.xml
  com.google.android.docksetup:settingslib_learn_more_text
)

export_arrays() {
  export EXCLUDE_OVERLAY_NAMES="${exclude_overlay_names[*]}"
  export KEEP_PACKAGE_NAMES="${keep_package_names[*]}"
  export KEEP_RESOURCE_NAMES="${keep_resource_names[*]}"
  export PREFER_RESOURCE_NAMES="${prefer_resource_names[*]}"
  export REMOVE_RESOURCE_NAMES="${remove_resource_names[*]}"
}

import_arrays() {
  read -r -a exclude_overlay_names <<< "${EXCLUDE_OVERLAY_NAMES:-}"
  read -r -a keep_package_names <<< "${KEEP_PACKAGE_NAMES:-}"
  read -r -a keep_resource_names <<< "${KEEP_RESOURCE_NAMES:-}"
  read -r -a prefer_resource_names <<< "${PREFER_RESOURCE_NAMES:-}"
  read -r -a remove_resource_names <<< "${REMOVE_RESOURCE_NAMES:-}"
}
export -f import_arrays

generate_rro() {
  import_arrays

  local device="${1}"
  source "${vars_path}/${device}"

  local dev_dir="${work_dir}/dev/${device}"
  local download_dir="${work_dir}/${device}/${build_id}"
  local factory_dir="${download_dir}/$(basename ${image_url} .zip)"

  pushd "${top}" > /dev/null

  if [ ! -d "${factory_dir}/product/overlay" ] && \
     [ ! -d "${factory_dir}/vendor/overlay" ] && \
     [ ! -f "${factory_dir}/system/framework/framework-res.apk" ]; then
    tools/extract-utils/extract.py --pixel-factory --pixel-firmware --all --download-dir ${download_dir} --download-sha256 ${image_sha256} ${image_url}
  fi
  if [ -d "${dev_dir}/overlay" ]; then
    rm -rf "${dev_dir}/overlay"
  fi

  local -a extra_args=()
  for o in "${exclude_overlay_names[@]}"; do
    extra_args+=(--exclude-overlay "$o")
  done

  lineage/scripts/dev/generate_rro.py \
      --device "${device}" \
      --dump "${factory_dir}" \
      --overlays "${dev_dir}/overlay" \
      "${extra_args[@]}"

  popd > /dev/null
}
export -f generate_rro

commonize_rro_one() {
  local dev_dir="${work_dir}/dev"

  local device="${1}"
  shift

  rm -rf "${dev_dir}/${device}/overlay"

  local -a overlays=()
  for d in "$@"; do
    overlays+=("${dev_dir}/${d}/overlay")
  done

  lineage/scripts/dev/commonize_rro.py \
      "${overlays[@]}" \
      --device "${device}" \
      --output "${dev_dir}/${device}/overlay"
}

commonize_rro_chain() {
  import_arrays

  case "$1" in
    gs101)
      commonize_rro_one raviole oriole raven
      commonize_rro_one gs101 raviole bluejay
      ;;
    gs201)
      commonize_rro_one pantah cheetah panther
      commonize_rro_one gs201 pantah lynx tangorpro felix
      ;;
    zuma)
      commonize_rro_one shusky husky shiba
      commonize_rro_one zuma shusky akita
      ;;
    zumapro)
      commonize_rro_one caimito caiman komodo tokay
      commonize_rro_one zumapro caimito comet tegu
      ;;
    laguna)
      commonize_rro_one muzel blazer frankel mustang
      commonize_rro_one laguna muzel rango
      ;;
  esac
}

commonize_rro() {
  pushd "${top}" >/dev/null || return 1

  export -f commonize_rro_one
  export -f commonize_rro_chain

  parallel --line-buffer --tag \
      commonize_rro_chain ::: \
      gs101 \
      gs201 \
      zuma \
      zumapro \
      laguna

  popd > /dev/null
}

beautify_rro_one() {
  local dev_dir="${work_dir}/dev"

  pushd "${top}" > /dev/null

  local -a extra_args=()
  for o in "${keep_package_names[@]}"; do
    extra_args+=(--keep-package "$o")
  done
  for o in "${keep_resource_names[@]}"; do
    extra_args+=(--keep-resource "$o")
  done
  for o in "${prefer_resource_names[@]}"; do
    extra_args+=(--prefer-resource "$o")
  done
  for o in "${remove_resource_names[@]}"; do
    extra_args+=(--remove-resource "$o")
  done
  for d in "$@"; do
    extra_args+=("${dev_dir}/${d}/overlay")
  done
  extra_args+=(--common vendor/lineage/overlay/rro_packages)

  lineage/scripts/dev/beautify_rro.py \
      "${extra_args[@]}"

  popd > /dev/null
}

beautify_rro_chain() {
  import_arrays

  case "$1" in
  gs101)
    beautify_rro_one oriole raven raviole bluejay gs101
    ;;
  gs201)
    beautify_rro_one cheetah panther pantah lynx tangorpro felix gs201
    ;;
  zuma)
    beautify_rro_one husky shiba shusky akita zuma
    ;;
  zumapro)
    beautify_rro_one caiman komodo tokay caimito comet tegu zumapro
    ;;
  laguna)
    beautify_rro_one blazer frankel mustang muzel rango laguna
    ;;
  esac
}

beautify_rro() {
  pushd "${top}" >/dev/null || return 1

  export -f beautify_rro_one
  export -f beautify_rro_chain

  parallel --line-buffer --tag \
      beautify_rro_chain ::: \
      gs101 \
      gs201 \
      zuma \
      zumapro \
      laguna

  popd >/dev/null
}

print_packages_rro_one() {
  local dev_dir="${work_dir}/dev"

  local -a overlays=()
  for d in "$@"; do
    overlays+=("${dev_dir}/${d}/overlay")
  done

  lineage/scripts/dev/print_packages_rro.py \
      "${overlays[@]}"
}

print_packages_rro() {
  pushd "${top}" >/dev/null || return 1

  print_packages_rro_one oriole raven raviole bluejay gs101

  print_packages_rro_one cheetah panther pantah lynx tangorpro felix gs201

  print_packages_rro_one husky shiba shusky akita zuma

  print_packages_rro_one caiman komodo tokay caimito comet tegu zumapro

  print_packages_rro_one blazer frankel mustang muzel rango laguna

  popd >/dev/null
}

# error message
# ARG1: error message for STDERR
# ARG2: error status
error_m() {
  echo "ERROR: ${1:-'failed.'}" 1>&2
  return "${2:-1}"
}

# print help message.
help_message() {
  echo "${help_message:-'No help available.'}"
}

main() {
  export_arrays

  if [[ $# -lt 1 ]] ; then
    error_m "No devices provided."
  else
    parallel --line-buffer --tag generate_rro ::: "${@}"
    commonize_rro
    beautify_rro
    print_packages_rro
  fi
}

### RUN PROGRAM ###

main "${@}"


##

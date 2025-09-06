#!/bin/bash

# SPDX-FileCopyrightText: The LineageOS Project
#
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

## HELP MESSAGE (USAGE INFO)
# TODO

### FUNCTIONS ###

dev() {
  local device="${1}"
  source "${vars_path}/${device}"

  local dev_dir="${work_dir}/dev/${device}"
  local download_dir="${work_dir}/${device}/${build_id}"
  local factory_dir="${download_dir}/$(basename ${image_url} .zip)"

  pushd "${top}"
  tools/extract-utils/extract.py --pixel-factory --pixel-firmware --all --download-dir ${download_dir} --download-sha256 ${image_sha256} ${image_url}
  if [ -d "${dev_dir}/overlays" ]; then
    rm -r "${dev_dir}/overlays"
  fi

  lineage/scripts/dev/generate_rro.py \
      "${factory_dir}/product/overlay" \
      --overlays "${dev_dir}/overlay/product" \
      --keep-package com.android.hbmsvmanager \
      --keep-package com.android.omadm.service \
      --keep-package com.android.pixeldisplayservice \
      --keep-package com.google.android.apps.scone \
      --keep-package com.google.android.docksetup \
      --keep-package com.google.android.grilservice \
      --keep-package com.google.euiccpixel \
      --keep-package com.shannon.imsservice \
      --exclude-overlay com.android.bips.overlay.product \
      --exclude-overlay com.android.captiveportallogin.overlay \
      --exclude-overlay com.android.cellbroadcastreceiver.overlay.pixel \
      --exclude-overlay com.android.cellbroadcastservice.overlay.pixel \
      --exclude-overlay com.android.healthconnect.overlay \
      --exclude-overlay com.android.managedprovisioning.overlay \
      --exclude-overlay com.android.providers.contacts.overlay.product \
      --exclude-overlay com.android.providers.media.overlay.pixel \
      --exclude-overlay com.android.simappdialog.overlay.product \
      --exclude-overlay com.android.systemui.accessibility.accessibilitymenu.overlay.product \
      --exclude-overlay com.google.android.documentsui.theme.pixel \
      --exclude-overlay com.google.android.pixel.avatarpicker \
      --exclude-overlay com.google.android.overlay.devicelockcontroller \
      --exclude-overlay com.google.android.overlay.googlewebview \
      --exclude-overlay com.google.android.overlay.permissioncontroller \
      --exclude-overlay com.google.android.overlay.trafficlightfaceoverlay \
      --exclude-overlay com.google.android.overlay.udfpsoverlay \
      --exclude-overlay com.google.android.settings.overlay.pixelvpnconfig \
      --exclude-overlay com.google.android.systemui.gxoverlay \
      --exclude-overlay com.google.android.verifier.overlay

  lineage/scripts/dev/generate_rro.py \
      "${factory_dir}/vendor/overlay" \
      --overlays "${dev_dir}/overlay/vendor" \
      --keep-package com.android.omadm.service \
      --keep-package com.google.android.docksetup

  lineage/scripts/dev/beautify_rro.py \
      "${dev_dir}/overlay/product" \
      --keep-package com.android.hbmsvmanager \
      --keep-package com.android.omadm.service \
      --keep-package com.android.pixeldisplayservice \
      --keep-package com.google.android.apps.scone \
      --keep-package com.google.android.docksetup \
      --keep-package com.google.android.grilservice \
      --keep-package com.google.euiccpixel \
      --keep-package com.shannon.imsservice \
      --remove-resource android:config_showGesturalNavigationHints \
      --remove-resource android:config_accessComputerControlKnownSigners \
      --remove-resource android:config_allowedSecureInstantAppSettings \
      --remove-resource android:config_appFunctionDeviceSettingsPackages \
      --remove-resource android:config_appsAuthorizedForSharedAccounts \
      --remove-resource android:config_backupHealthConnectDataAndSettingsKnownSigners \
      --remove-resource android:config_companionDeviceCerts \
      --remove-resource android:config_companionDevicePackages \
      --remove-resource android:config_defaultAccessibilityNotificationSound \
      --remove-resource android:config_defaultAccessibilityService \
      --remove-resource android:config_defaultAppFunctionAgentAllowlist \
      --remove-resource android:config_defaultAssistant \
      --remove-resource android:config_defaultAutofillService \
      --remove-resource android:config_defaultCaptivePortalLoginPackageName \
      --remove-resource android:config_defaultCredentialManagerHybridService \
      --remove-resource android:config_defaultDialer \
      --remove-resource android:config_defaultDockManagerPackageName \
      --remove-resource android:config_defaultListenerAccessPackages \
      --remove-resource android:config_defaultNearbyFastPairSettingsDevicesComponent \
      --remove-resource android:config_defaultNearbySharingComponent \
      --remove-resource android:config_defaultNetworkRecommendationProviderPackage \
      --remove-resource android:config_defaultQrCodeComponent \
      --remove-resource android:config_defaultSearchSelectorPackageName \
      --remove-resource android:config_defaultSelectToSpeakService \
      --remove-resource android:config_defaultSms \
      --remove-resource android:config_defaultVoiceAccessService \
      --remove-resource android:config_defaultWallet \
      --remove-resource android:config_deviceConfiguratorPackageName \
      --remove-resource android:config_devicePolicyManagement \
      --remove-resource android:config_devicePolicyManagementUpdater \
      --remove-resource android:config_disabledUntilUsedPreinstalledImes \
      --remove-resource android:config_enablePrimaryLocationTimeZoneProvider \
      --remove-resource android:config_enabledCredentialProviderService \
      --remove-resource android:config_ephemeralResolverPackage \
      --remove-resource android:config_face_acquire_biometricprompt_ignorelist \
      --remove-resource android:config_face_acquire_enroll_ignorelist \
      --remove-resource android:config_face_acquire_keyguard_ignorelist \
      --remove-resource android:config_face_acquire_vendor_biometricprompt_ignorelist \
      --remove-resource android:config_face_acquire_vendor_enroll_ignorelist \
      --remove-resource android:config_face_acquire_vendor_keyguard_ignorelist \
      --remove-resource android:config_fontManagerServiceCerts \
      --remove-resource android:config_forceQueryablePackages \
      --remove-resource android:config_healthConnectMigrationKnownSigners \
      --remove-resource android:config_healthConnectMigratorPackageName \
      --remove-resource android:config_healthConnectRestoreKnownSigners \
      --remove-resource android:config_help_url_action_disabled_by_advanced_protection \
      --remove-resource android:config_integrityRuleProviderPackages \
      --remove-resource android:config_intrusionDetectionEventTransport \
      --remove-resource android:config_loggable_dream_prefixes \
      --remove-resource android:config_notificationDefaultUnsupportedAdjustments \
      --remove-resource android:config_oemCredentialManagerDialogComponent \
      --remove-resource android:config_persistentDataPackageName \
      --remove-resource android:config_primaryCredentialProviderService \
      --remove-resource android:config_primaryLocationTimeZoneProviderPackageName \
      --remove-resource android:config_restoreHealthConnectDataAndSettingsKnownSigners \
      --remove-resource android:config_servicesExtensionPackage \
      --remove-resource android:config_settingsHelpLinksEnabled \
      --remove-resource android:config_sharedConnectivityServiceIntentAction \
      --remove-resource android:config_sharedConnectivityServicePackage \
      --remove-resource android:config_shortPressOnPowerBehavior \
      --remove-resource android:config_systemActivityRecognizer \
      --remove-resource android:config_systemAutomotiveProjection \
      --remove-resource android:config_systemBluetoothStack \
      --remove-resource android:config_systemCallStreaming \
      --remove-resource android:config_systemCompanionDeviceProvider \
      --remove-resource android:config_systemContacts \
      --remove-resource android:config_systemDependencyInstaller \
      --remove-resource android:config_systemFinancedDeviceController \
      --remove-resource android:config_systemGallery \
      --remove-resource android:config_systemGameService \
      --remove-resource android:config_systemSettingsIntelligence \
      --remove-resource android:config_systemSpeechRecognizer \
      --remove-resource android:config_trustedAccessibilityServices \
      --remove-resource android:face_acquired_vendor \
      --remove-resource android:face_error_vendor \
      --remove-resource android:identity_check_settings_action \
      --remove-resource android:identity_check_settings_package_name \
      --remove-resource android:proximity_provider_service_class_name \
      --remove-resource android:proximity_provider_service_package_name \
      --remove-resource android:safety_protection_display_text \
      --remove-resource android:trusted_location_settings_action \
      --remove-resource android:widget_default_class_name \
      --remove-resource android:widget_default_package_name \
      --remove-resource android:biometric_app_setting_name \
      --remove-resource android:biometric_dialog_default_subtitle \
      --remove-resource android:biometric_or_screen_lock_app_setting_name \
      --remove-resource android:biometric_or_screen_lock_dialog_default_subtitle \
      --remove-resource android:face_recalibrate_notification_content \
      --remove-resource android:face_recalibrate_notification_name \
      --remove-resource android:face_recalibrate_notification_title \
      --remove-resource android:harmful_app_warning_title \
      --remove-resource android:scCellularNetworkSecurityLearnMore \
      --remove-resource android:vendor_cross_profile_apps \
      --remove-resource android:vendor_disallowed_apps_managed_device \
      --remove-resource android:vendor_disallowed_apps_managed_profile \
      --remove-resource android:vendor_disallowed_apps_managed_user \
      --remove-resource android:vendor_required_apps_managed_device \
      --remove-resource android:vendor_required_apps_managed_profile \
      --remove-resource android:vendor_required_apps_managed_user \
      --remove-resource android:vendor_required_attestation_certificates \
      --remove-resource android:vendor_required_attestation_revocation_list_url \
      --remove-resource android:bookmarks.xml \
      --remove-resource android:config_assistLongPressHomeEnabledDefault \
      --remove-resource android:config_assistTouchGestureEnabledDefault \
      --remove-resource android:config_defaultDndAccessPackages \
      --remove-resource android:config_defaultNightMode \
      --remove-resource android:config_dreamsDefaultComponent \
      --remove-resource android:config_volumeHushGestureEnabled \
      --remove-resource android:config_progress_background_tint.xml \
      --remove-resource android:ic_doc_apk.xml \
      --remove-resource android:ic_doc_audio.xml \
      --remove-resource android:ic_doc_certificate.xml \
      --remove-resource android:ic_doc_codes.xml \
      --remove-resource android:ic_doc_compressed.xml \
      --remove-resource android:ic_doc_contact.xml \
      --remove-resource android:ic_doc_document.xml \
      --remove-resource android:ic_doc_event.xml \
      --remove-resource android:ic_doc_excel.xml \
      --remove-resource android:ic_doc_folder.xml \
      --remove-resource android:ic_doc_font.xml \
      --remove-resource android:ic_doc_generic.xml \
      --remove-resource android:ic_doc_image.xml \
      --remove-resource android:ic_doc_pdf.xml \
      --remove-resource android:ic_doc_powerpoint.xml \
      --remove-resource android:ic_doc_presentation.xml \
      --remove-resource android:ic_doc_spreadsheet.xml \
      --remove-resource android:ic_doc_text.xml \
      --remove-resource android:ic_doc_video.xml \
      --remove-resource android:ic_doc_word.xml \
      --remove-resource android:user_icon_1 \
      --remove-resource android:error_color_device_default_dark \
      --remove-resource android:error_color_device_default_light \
      --remove-resource android:config_ambientContextEventArrayExtraKey \
      --remove-resource android:config_ambientContextPackageNameExtraKey \
      --remove-resource android:config_batteryPackageTypeService \
      --remove-resource android:config_bodyFontFamily \
      --remove-resource android:config_bodyFontFamilyMedium \
      --remove-resource android:config_bugReportHandlerEnabled \
      --remove-resource android:config_buttonTextAllCaps \
      --remove-resource android:config_clockFontFamily \
      --remove-resource android:config_defaultAmbientContextConsentComponent \
      --remove-resource android:config_defaultAmbientContextDetectionService \
      --remove-resource android:config_defaultAssistantAccessComponent \
      --remove-resource android:config_defaultAugmentedAutofillService \
      --remove-resource android:config_defaultBugReportHandlerApp \
      --remove-resource android:config_defaultCloudSearchServices \
      --remove-resource android:config_defaultContentCaptureService \
      --remove-resource android:config_defaultContentProtectionService \
      --remove-resource android:config_defaultContextualSearchEnabled \
      --remove-resource android:config_defaultContextualSearchKey \
      --remove-resource android:config_defaultContextualSearchLegacyEnabled \
      --remove-resource android:config_defaultContextualSearchPackageName \
      --remove-resource android:config_defaultFieldClassificationService \
      --remove-resource android:config_defaultModuleMetadataProvider \
      --remove-resource android:config_defaultMusicRecognitionService \
      --remove-resource android:config_defaultOnDeviceIntelligenceDeviceConfigNamespace \
      --remove-resource android:config_defaultOnDeviceIntelligenceService \
      --remove-resource android:config_defaultOnDeviceSandboxedInferenceService \
      --remove-resource android:config_defaultOnDeviceSpeechRecognitionService \
      --remove-resource android:config_defaultProfcollectReportUploaderAction \
      --remove-resource android:config_defaultProfcollectReportUploaderApp \
      --remove-resource android:config_defaultRetailDemo \
      --remove-resource android:config_defaultRingtonePickerEnabled \
      --remove-resource android:config_defaultSearchUiService \
      --remove-resource android:config_defaultSmartspaceService \
      --remove-resource android:config_defaultSupervisionProfileOwnerComponent \
      --remove-resource android:config_defaultTextClassifierPackage \
      --remove-resource android:config_defaultTranslationService \
      --remove-resource android:config_defaultWallpaperEffectsGenerationService \
      --remove-resource android:config_emergency_dialer_package \
      --remove-resource android:config_faceAuthDismissesKeyguard \
      --remove-resource android:config_feedbackIntentExtraKey \
      --remove-resource android:config_feedbackIntentNameKey \
      --remove-resource android:config_headlineFontFamily \
      --remove-resource android:config_headlineFontFamilyMedium \
      --remove-resource android:config_headlineFontFeatureSettings \
      --remove-resource android:config_helpIntentExtraKey \
      --remove-resource android:config_helpIntentNameKey \
      --remove-resource android:config_helpPackageNameKey \
      --remove-resource android:config_helpPackageNameValue \
      --remove-resource android:config_icon_mask \
      --remove-resource android:config_incidentReportApproverPackage \
      --remove-resource android:config_longPressOnHomeBehavior \
      --remove-resource android:config_packagesExemptFromSuspension \
      --remove-resource android:config_powerSaveModeChangedListenerPackage \
      --remove-resource android:config_preferredSystemImageEditor \
      --remove-resource android:config_priorityOnlyDndExemptPackages \
      --remove-resource android:config_profcollectOnCameraOpenedSkipPackages \
      --remove-resource android:config_profcollectReportUploaderEnabled \
      --remove-resource android:config_rawContactsEligibleDefaultAccountTypes \
      --remove-resource android:config_recentsComponentName \
      --remove-resource android:config_retailDemoPackage \
      --remove-resource android:config_retailDemoPackageSignature \
      --remove-resource android:config_secondaryHomePackage \
      --remove-resource android:config_sendPackageName \
      --remove-resource android:config_setContactsDefaultAccountKnownSigners \
      --remove-resource android:config_smart_battery_available \
      --remove-resource android:config_storageManagerDaystoRetainDefault \
      --remove-resource android:config_supportDoubleTapSleep \
      --remove-resource android:config_supportLongPressPowerWhenNonInteractive \
      --remove-resource android:config_supportsCamToggle \
      --remove-resource android:config_supportsMicToggle \
      --remove-resource android:config_systemAppProtectionService \
      --remove-resource android:config_systemCaptionsServiceCallsEnabled \
      --remove-resource android:config_systemImageEditor \
      --remove-resource android:config_systemSupervision \
      --remove-resource android:config_systemWellbeing \
      --remove-resource android:android_start_title \
      --remove-resource android:android_upgrading_title \
      --remove-resource android:default_wallpaper.png \
      --remove-resource android:config_defaultFirstUserRestrictions \
      --remove-resource android:config_deviceProvisioningPackage \
      --remove-resource android:config_locationExtraPackageNames \
      --remove-resource android:config_locationProviderPackageNames \
      --remove-resource android:config_notificationVibrationPatternToMetricIdMapping \
      --remove-resource android:config_repairModeSupported \
      --remove-resource android:config_ringtoneVibrationPatternToMetricIdMapping \
      --remove-resource android:config_wallpaperCropperPackage \
      --remove-resource android:config_hideWhenDisabled_packageNames \
      --remove-resource android:config_mobile_hotspot_provision_app \
      --remove-resource android:config_mobile_hotspot_provision_app_no_ui \
      --remove-resource android:config_mobile_hotspot_provision_response \
      --remove-resource com.android.connectivity.resources:config_activelyPreferBadWifi \
      --remove-resource com.android.devicediagnostics:config_avatar_picker_package \
      --remove-resource com.android.devicediagnostics:config_hspa_data_distinguishable \
      --remove-resource com.android.devicediagnostics:config_showMin3G \
      --remove-resource com.android.devicediagnostics:data_connection_5g_plus \
      --remove-resource com.android.devicediagnostics:ic_5g_plus_mobiledata.xml \
      --remove-resource com.android.devicediagnostics:ic_5g_plus_mobiledata_updated.xml \
      --remove-resource com.android.networkstack.tethering:config_mobile_hotspot_provision_app \
      --remove-resource com.android.networkstack.tethering:config_mobile_hotspot_provision_app_no_ui \
      --remove-resource com.android.networkstack.tethering:config_mobile_hotspot_provision_response \
      --remove-resource com.android.omadm.service:config_omadm_metrics_enabled \
      --remove-resource com.android.omadm.service:config_omadm_metrics_app_package \
      --remove-resource com.android.omadm.service:config_omadm_metrics_class_name \
      --remove-resource com.android.omadm.service:config_omadm_metrics_extra_log_bytes \
      --remove-resource com.android.omadm.service:config_omadm_metrics_extra_log_source \
      --remove-resource com.android.omadm.service:config_omadm_metrics_intent_action \
      --remove-resource com.android.phone:carrier_settings \
      --remove-resource com.android.phone:carrier_settings_menu \
      --remove-resource com.android.phone:dialer_default_class \
      --remove-resource com.android.phone:platform_number_verification_package \
      --remove-resource com.android.phone:incall_error_promote_wfc \
      --remove-resource com.android.phone:status_hint_label_incoming_wifi_call \
      --remove-resource com.android.phone:status_hint_label_wifi_call \
      --remove-resource com.android.phone:wifi_calling \
      --remove-resource com.android.phone:wifi_calling_settings_title \
      --remove-resource com.android.phone:config_apn_expand \
      --remove-resource com.android.phone:config_carrier_settings_enable \
      --remove-resource com.android.phone:config_show_cdma \
      --remove-resource com.android.phone:config_use_hfa_for_provisioning \
      --remove-resource com.android.phone:support_swap_after_merge \
      --remove-resource com.android.providers.settings:def_backup_transport \
      --remove-resource com.android.providers.settings:def_double_tap_to_sleep \
      --remove-resource com.android.providers.settings:def_screen_off_timeout \
      --remove-resource com.android.providers.settings:def_vibrate_when_ringing \
      --remove-resource com.android.providers.settings:def_wireless_charging_started_sound \
      --remove-resource com.android.server.telecom:call_diagnostic_service_package_name \
      --remove-resource com.android.server.telecom:dialer_default_class \
      --remove-resource com.android.settings:config_avatar_picker_package \
      --remove-resource com.android.settings:config_hspa_data_distinguishable \
      --remove-resource com.android.settings:config_settings_slices_accessibility_components \
      --remove-resource com.android.settings:config_showMin3G \
      --remove-resource com.android.settings:data_connection_5g_plus \
      --remove-resource com.android.settings:display_white_balance_summary \
      --remove-resource com.android.settings:display_white_balance_title \
      --remove-resource com.android.settings:face_education.mp4 \
      --remove-resource com.android.settings:fingerprint_location_animation.mp4 \
      --remove-resource com.android.settings:fingerprint_unlock_set_unlock_password \
      --remove-resource com.android.settings:fingerprint_unlock_set_unlock_pattern \
      --remove-resource com.android.settings:fingerprint_unlock_set_unlock_pin \
      --remove-resource com.android.settings:fingerprint_unlock_skip_fingerprint \
      --remove-resource com.android.settings:fingerprint_unlock_title \
      --remove-resource com.android.settings:icon_accent \
      --remove-resource com.android.settings:ic_5g_plus_mobiledata.xml \
      --remove-resource com.android.settings:ic_5g_plus_mobiledata_updated.xml \
      --remove-resource com.android.settings:peak_refresh_rate_summary \
      --remove-resource com.android.settings:security_settings_fingerprint_enroll_consent_introduction_title \
      --remove-resource com.android.settings:security_settings_fingerprint_enroll_introduction_message_unlock_disabled \
      --remove-resource com.android.settings:security_settings_fingerprint_enroll_introduction_title \
      --remove-resource com.android.settings:security_settings_fingerprint_enroll_introduction_title_unlock_disabled \
      --remove-resource com.android.settings:security_settings_fingerprint_preference_title \
      --remove-resource com.android.settings:shortcut_base.png \
      --remove-resource com.android.settings:slice_allowlist_package_names \
      --remove-resource com.android.settings:slice_allowlist_package_names_for_dev \
      --remove-resource com.android.settings:suggested_fingerprint_lock_settings_summary \
      --remove-resource com.android.storagemanager:config_avatar_picker_package \
      --remove-resource com.android.storagemanager:config_hspa_data_distinguishable \
      --remove-resource com.android.storagemanager:config_showMin3G \
      --remove-resource com.android.storagemanager:data_connection_5g_plus \
      --remove-resource com.android.storagemanager:ic_5g_plus_mobiledata.xml \
      --remove-resource com.android.storagemanager:ic_5g_plus_mobiledata_updated.xml \
      --remove-resource com.android.systemui:ambientcue_first_time_edu_text \
      --remove-resource com.android.systemui:config_avatar_picker_package \
      --remove-resource com.android.systemui:config_controlsPreferredPackages \
      --remove-resource com.android.systemui:config_face_auth_props \
      --remove-resource com.android.systemui:config_hspa_data_distinguishable \
      --remove-resource com.android.systemui:config_pluginAllowlist \
      --remove-resource com.android.systemui:config_preferredScreenshotEditor \
      --remove-resource com.android.systemui:config_remoteCopyPackage \
      --remove-resource com.android.systemui:config_screenshotEditor \
      --remove-resource com.android.systemui:config_screenshotFilesApp \
      --remove-resource com.android.systemui:config_showMin3G \
      --remove-resource com.android.systemui:data_connection_5g_plus \
      --remove-resource com.android.systemui:ic_5g_plus_mobiledata.xml \
      --remove-resource com.android.systemui:ic_5g_plus_mobiledata_updated.xml \
      --remove-resource com.android.systemui:stat_sys_branded_vpn.xml \
      --remove-resource com.android.traceur:config_avatar_picker_package \
      --remove-resource com.android.traceur:config_hspa_data_distinguishable \
      --remove-resource com.android.traceur:config_showMin3G \
      --remove-resource com.android.traceur:data_connection_5g_plus \
      --remove-resource com.android.traceur:ic_5g_plus_mobiledata.xml \
      --remove-resource com.android.traceur:ic_5g_plus_mobiledata_updated.xml

  lineage/scripts/dev/beautify_rro.py \
      "${dev_dir}/overlay/vendor" \
      --keep-package com.android.omadm.service \
      --keep-package com.google.android.docksetup \
      --remove-resource android:config_doubleTapPowerGestureMode \
      --remove-resource android:config_pinnerCameraApp \
      --remove-resource android:config_tether_usb_regexs \
      --remove-resource android:config_tether_wifi_regexs \
      --remove-resource android:quick_qs_offset_height \
      --remove-resource com.android.devicediagnostics:ic_5g_plus_mobiledata.xml \
      --remove-resource com.android.devicediagnostics:ic_5g_plus_mobiledata_updated.xml \
      --remove-resource com.android.settings:config_network_selection_list_aggregation_enabled \
      --remove-resource com.android.settings:ic_5g_plus_mobiledata.xml \
      --remove-resource com.android.settings:ic_5g_plus_mobiledata_updated.xml \
      --remove-resource com.android.storagemanager:ic_5g_plus_mobiledata.xml \
      --remove-resource com.android.storagemanager:ic_5g_plus_mobiledata_updated.xml \
      --remove-resource com.android.systemui:ic_5g_plus_mobiledata.xml \
      --remove-resource com.android.systemui:ic_5g_plus_mobiledata_updated.xml \
      --remove-resource com.android.systemui:status_bar_height \
      --remove-resource com.android.traceur:ic_5g_plus_mobiledata.xml \
      --remove-resource com.android.traceur:ic_5g_plus_mobiledata_updated.xml

  popd
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
  if [[ $# -eq 1 ]] ; then
    dev "${1}"
  else
    error_m
  fi
}

### RUN PROGRAM ###

main "${@}"


##

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

exclude_overlay_name=(
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

keep_package_names=(
  com.android.hbmsvmanager
  com.android.omadm.service
  com.android.pixeldisplayservice
  com.google.android.apps.scone
  com.google.android.docksetup
  com.google.android.grilservice
  com.google.euiccpixel
  com.shannon.imsservice
)

keep_resource_names=(
  "com.android.settings:regulatory_info_*"
)

remove_resource_names=(
  android:android_start_title
  android:android_upgrading_title
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
  android:config_locationExtraPackageNames
  android:config_locationProviderPackageNames
  android:config_loggable_dream_prefixes
  android:config_longPressOnHomeBehavior
  android:config_mobile_hotspot_provision_app
  android:config_mobile_hotspot_provision_app_no_ui
  android:config_mobile_hotspot_provision_response
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
  android:config_volumeHushGestureEnabled
  android:config_wallpaperCropperPackage
  android:default_wallpaper.png
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
  com.android.devicediagnostics:ic_5g_plus_mobiledata.xml
  com.android.devicediagnostics:ic_5g_plus_mobiledata_updated.xml
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
  com.android.settings:data_connection_5g_plus
  com.android.settings:display_white_balance_summary
  com.android.settings:display_white_balance_title
  com.android.settings:face_education.mp4
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
  com.android.settings:ic_5g_plus_mobiledata.xml
  com.android.settings:ic_5g_plus_mobiledata_updated.xml
  com.android.settings:icon_accent
  com.android.settings:peak_refresh_rate_summary
  com.android.settings:security_settings_fingerprint_enroll_consent_introduction_title
  com.android.settings:security_settings_fingerprint_enroll_introduction_message_unlock_disabled
  com.android.settings:security_settings_fingerprint_enroll_introduction_title
  com.android.settings:security_settings_fingerprint_enroll_introduction_title_unlock_disabled
  com.android.settings:security_settings_fingerprint_preference_title
  com.android.settings:security_settings_fingerprint_v2_enroll_introduction_footer_message_6
  com.android.settings:security_settings_udfps_enroll_fingertip_title
  com.android.settings:security_settings_udfps_enroll_left_edge_title
  com.android.settings:security_settings_udfps_enroll_right_edge_title
  com.android.settings:shortcut_base.png
  com.android.settings:slice_allowlist_package_names
  com.android.settings:slice_allowlist_package_names_for_dev
  com.android.settings:suggested_fingerprint_lock_settings_summary
  com.android.storagemanager:config_avatar_picker_package
  com.android.storagemanager:config_hspa_data_distinguishable
  com.android.storagemanager:config_showMin3G
  com.android.storagemanager:data_connection_5g_plus
  com.android.storagemanager:ic_5g_plus_mobiledata.xml
  com.android.storagemanager:ic_5g_plus_mobiledata_updated.xml
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
  com.android.systemui:stat_sys_branded_vpn.xml
  com.android.systemui:status_bar_height
  com.android.traceur:config_avatar_picker_package
  com.android.traceur:config_hspa_data_distinguishable
  com.android.traceur:config_showMin3G
  com.android.traceur:data_connection_5g_plus
  com.android.traceur:ic_5g_plus_mobiledata.xml
  com.android.traceur:ic_5g_plus_mobiledata_updated.xml
)

generate_rro() {
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
    rm -r "${dev_dir}/overlay"
  fi

  extra_args=()
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

commonize_rro() {
  local dev_dir="${work_dir}/dev"

  pushd "${top}" > /dev/null

  for family in "$@"; do
    if [ -d "${dev_dir}/${family}/overlay" ]; then
      rm -rf "${dev_dir}/${family}/overlay"
    fi
  done

  (
    lineage/scripts/dev/commonize_rro.py \
        "${dev_dir}/oriole/overlay" "${dev_dir}/raven/overlay" \
        --device raviole \
        --output "${dev_dir}/raviole/overlay"
    lineage/scripts/dev/commonize_rro.py \
        "${dev_dir}/raviole/overlay" "${dev_dir}/bluejay/overlay" \
        --device gs101 \
        --output "${dev_dir}/gs101/overlay"
  ) &
  (
    lineage/scripts/dev/commonize_rro.py \
        "${dev_dir}/cheetah/overlay" "${dev_dir}/panther/overlay" \
        --device pantah \
        --output "${dev_dir}/pantah/overlay"
    lineage/scripts/dev/commonize_rro.py \
        "${dev_dir}/pantah/overlay" "${dev_dir}/lynx/overlay" "${dev_dir}/tangorpro/overlay" "${dev_dir}/felix/overlay" \
        --device gs201 \
        --output "${dev_dir}/gs201/overlay"
  ) &
  (
    lineage/scripts/dev/commonize_rro.py \
        "${dev_dir}/husky/overlay" "${dev_dir}/shiba/overlay" \
        --device shusky \
        --output "${dev_dir}/shusky/overlay"
    lineage/scripts/dev/commonize_rro.py \
        "${dev_dir}/shusky/overlay" "${dev_dir}/akita/overlay" \
        --device zuma \
        --output "${dev_dir}/zuma/overlay"
  ) &
  (
    lineage/scripts/dev/commonize_rro.py \
        "${dev_dir}/caiman/overlay" "${dev_dir}/komodo/overlay" "${dev_dir}/tokay/overlay" \
        --device caimito \
        --output "${dev_dir}/caimito/overlay"
    lineage/scripts/dev/commonize_rro.py \
        "${dev_dir}/caimito/overlay" "${dev_dir}/comet/overlay" "${dev_dir}/tegu/overlay" \
        --device zumapro \
        --output "${dev_dir}/zumapro/overlay"
  ) &
  (
    lineage/scripts/dev/commonize_rro.py \
        "${dev_dir}/blazer/overlay" "${dev_dir}/frankel/overlay" "${dev_dir}/mustang/overlay" \
        --device muzel \
        --output "${dev_dir}/muzel/overlay"
    lineage/scripts/dev/commonize_rro.py \
        "${dev_dir}/muzel/overlay" "${dev_dir}/rango/overlay" \
        --device laguna \
        --output "${dev_dir}/laguna/overlay"
  ) &
  wait

  popd > /dev/null
}

beautify_rro() {
  local device="${1}"

  local dev_dir="${work_dir}/dev/${device}"

  pushd "${top}" > /dev/null

  extra_args=()
  for o in "${keep_package_names[@]}"; do
    extra_args+=(--keep-package "$o")
  done
  for o in "${keep_resource_names[@]}"; do
    extra_args+=(--keep-resource "$o")
  done
  for o in "${remove_resource_names[@]}"; do
    extra_args+=(--remove-resource "$o")
  done

  lineage/scripts/dev/beautify_rro.py \
      "${dev_dir}/overlay" \
      "${extra_args[@]}"

  popd > /dev/null
}
export -f beautify_rro

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
  if [[ $# -lt 1 ]] ; then
    error_m "No devices provided."
  else
    local common_families=("raviole" "gs101" "pantah" "gs201" "shusky" "zuma" "caimito" "zumapro" "muzel" "laguna")
    parallel --line-buffer --tag generate_rro ::: "${@}"
    commonize_rro "${common_families[@]}"
    parallel --line-buffer --tag beautify_rro ::: "${@}" "${common_families[@]}"
  fi
}

### RUN PROGRAM ###

main "${@}"


##

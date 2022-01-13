#!/bin/bash
#
# extract:
#
#   Setup pixel firmware
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
readonly vars_path="${script_path}/../vars"
readonly top="${script_path}/../../.."

readonly extract_ota_py="${top}/tools/extract-utils/extract_ota.py"

readonly work_dir="${WORK_DIR:-/tmp/pixel}"

source "${vars_path}/devices"

readonly device="${1}"
source "${vars_path}/${device}"

readonly factory_dir="${work_dir}/${device}/${build_id}/factory/${device}-${build_id,,}"
readonly ota_zip="${work_dir}/${device}/${build_id}/$(basename ${ota_url})"
readonly ota_firmware_dir="${work_dir}/${device}/${build_id}/firmware"

readonly vendor_path="${top}/vendor/firmware/${device}"

## HELP MESSAGE (USAGE INFO)
# TODO

### FUNCTIONS ###

# Unpack the seperate partitions needed for OTA
# from the factory image's bootloader.img
unpack_firmware() {
  # modem.img
  qc_image_unpacker -i "${factory_dir}"/radio-*.img -o "${ota_firmware_dir}"
  # All other ${firmware_partitions[@]}
  qc_image_unpacker -i "${factory_dir}"/bootloader-*.img -o "${ota_firmware_dir}"
}

extract_firmware() {
  echo "${ota_sha256} ${ota_zip}" | sha256sum --check --status
  python3 ${extract_ota_py} ${ota_zip} -o "${ota_firmware_dir}" -p ${firmware_partitions[@]}
}

# Firmware included in OTAs, separate partitions
# Can be extracted from bootloader.img inside the factory image,
# or directly from the OTA zip
copy_ota_firmware() {
  for fp in ${firmware_partitions[@]}; do
    cp "${ota_firmware_dir}/${fp}.img" "${vendor_path}/radio/${fp}.img"
  done
}

setup_makefiles() {
  echo "AB_OTA_PARTITIONS += \\" > "${vendor_path}/config.mk"
  for fp in ${firmware_partitions[@]}; do
    echo "    ${fp} \\" >> "${vendor_path}/config.mk"
  done

  echo "LOCAL_PATH := \$(call my-dir)" > "${vendor_path}/firmware.mk"
  echo >> "${vendor_path}/firmware.mk"
  echo "ifeq (\$(TARGET_DEVICE),${device})" >> "${vendor_path}/firmware.mk"
  for fp in ${firmware_partitions[@]}; do
    echo "\$(call add-radio-file,radio/${fp}.img)" >> "${vendor_path}/firmware.mk"
  done
  echo "endif" >> "${vendor_path}/firmware.mk"
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
  rm -rf "${ota_firmware_dir}"
  mkdir -p "${ota_firmware_dir}"
  rm -rf "${vendor_path}/radio"
  mkdir -p "${vendor_path}/radio"

  # Not all devices need OTA, most are supported in image_unpacker
  if [[ -n ${needs_ota-} ]]; then
    extract_firmware
  else
    unpack_firmware
  fi
  copy_ota_firmware
  setup_makefiles
}

### RUN PROGRAM ###

main "${@}"


##

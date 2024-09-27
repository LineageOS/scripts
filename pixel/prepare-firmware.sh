#!/bin/bash

# SPDX-FileCopyrightText: 2022-2023 The Calyx Institute
#
# SPDX-License-Identifier: Apache-2.0

#
# prepare-firmware:
#
#   Pixel firmware preparation hook for extract-utils
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

readonly fbpacktool="${top}/lineage/scripts/fbpacktool/fbpacktool.py"
readonly qc_image_unpacker="${top}/prebuilts/extract-tools/linux-x86/bin/qc_image_unpacker"

readonly device="${1}"
source "${vars_path}/${device}"

readonly _wifi_only="${wifi_only:-false}"

readonly src_dir="${2}"

## HELP MESSAGE (USAGE INFO)
# TODO

### FUNCTIONS ###

# Unpack the seperate partitions needed for OTA
# from the factory image's bootloader.img & radio.img
unpack_firmware() {
  if [[ "${_wifi_only}" != "true" ]]; then
    python3 "${fbpacktool}" unpack -o "${src_dir}" "${src_dir}"/radio-*.img
  fi

  python3 "${fbpacktool}" unpack -o "${src_dir}" "${src_dir}"/bootloader-*.img
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
  unpack_firmware
}

### RUN PROGRAM ###

main "${@}"


##

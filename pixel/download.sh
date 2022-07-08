#!/bin/bash

# SPDX-FileCopyrightText: 2022 The Calyx Institute
#
# SPDX-License-Identifier: Apache-2.0

#
# download:
#
#   Download Pixel factory images and OTA updates from Google
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

readonly work_dir="${WORK_DIR:-/tmp/pixel}"

source "${vars_path}/pixels"

readonly device="${1}"
source "${vars_path}/${device}"

## HELP MESSAGE (USAGE INFO)
# TODO

### FUNCTIONS ###

download_factory_image() {
  local factory_dir="${work_dir}/${device}/${build_id}"
  mkdir -p "${factory_dir}"
  local output="${factory_dir}/$(basename ${image_url})"
  curl --http1.1 -C - -L -o "${output}" "${image_url}"
  echo "${image_sha256} ${output}" | sha256sum --check --status
}

download_ota_zip() {
  local ota_dir="${work_dir}/${device}/${build_id}"
  mkdir -p "${ota_dir}"
  local output="${ota_dir}/$(basename ${ota_url})"
  curl --http1.1 -C - -L -o "${output}" "${ota_url}"
  echo "${ota_sha256} ${output}" | sha256sum --check --status
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
  download_factory_image
  # Not all devices need OTA, most are supported in image_unpacker
  if [[ -n ${needs_ota-} ]]; then
    download_ota_zip
  fi
}

### RUN PROGRAM ###

main "${@}"


##

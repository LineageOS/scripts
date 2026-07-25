#!/bin/bash

# SPDX-FileCopyrightText: 2023 The Calyx Institute
#
# SPDX-License-Identifier: Apache-2.0

#
# info:
#
#   Dump information for one device
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
readonly top="${script_path}/../../.."
readonly avbtool="${top}/external/avb/avbtool.py"

## HELP MESSAGE (USAGE INFO)
# TODO

### FUNCTIONS ###

get_prop() {
  local prop_name="$1"
  local prop_file="$2"

  if [[ -f "$prop_file" ]]; then
    grep "^${prop_name}=" "$prop_file" | cut -d'=' -f2- | tr -d '\r' || true
  fi
}

info() {
  local source="${1}"
  local system_prop="${source}/system/build.prop"
  local system_ext_prop="${source}/system_ext/etc/build.prop"
  local vendor_prop="${source}/vendor/build.prop"

  local manufacturer=$(get_prop "ro.product.system.manufacturer" "$system_prop")
  local name=$(get_prop "ro.product.system.name" "$system_prop")
  local device=$(get_prop "ro.product.system.device" "$system_prop")
  local release=$(get_prop "ro.system.build.version.release" "$system_prop")
  local system_incremental=$(get_prop "ro.system.build.version.incremental" "$system_prop")
  local type=$(get_prop "ro.system.build.type" "$system_prop")
  local tags=$(get_prop "ro.system.build.tags" "$system_prop")

  local platform_id=$(get_prop "ro.mot.platform.build_id" "$system_ext_prop")

  local build_id=$(get_prop "ro.vendor.build.id" "$vendor_prop")
  local vendor_incremental=$(get_prop "ro.vendor.build.version.incremental" "$vendor_prop")

  local security_patch=$(python3 ${avbtool} info_image --image ${source}/vbmeta.img | grep "com.android.build.vendor.security_patch" | cut -c 54- | sed s/\'//g)
  local rollback_index=$(python3 ${avbtool} info_image --image ${source}/vbmeta.img | grep "Rollback Index:" | cut -c 27-)

  local build_fingerprint="${manufacturer}/${name}/${device}:${release}/${build_id}/${system_incremental}-${vendor_incremental}:${type}/${tags}"

  local build_description="${name}-${type} ${release} ${build_id} ${system_incremental}-${vendor_incremental} ${tags}"
  if [[ -n "$platform_id" ]]; then
    build_description="${build_description} ${platform_id}"
  fi

  echo "Build ID:              $build_id"
  echo "Build fingerprint:     $build_fingerprint"
  echo "Build description:     $build_description"
  echo "Vendor security patch: $security_patch"
  echo "AVB rollback index:    $rollback_index"
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
    info "${1}"
  else
    error_m
  fi
}

### RUN PROGRAM ###

main "${@}"


##

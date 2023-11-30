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

info() {
  local source="${1}"

  local bootloader_version=$(cat ${source}/*.info.txt | grep "MBM Version:" | cut -c 14-)
  local build_id=$(cat ${source}/*.info.txt | grep "Build Id:" | cut -c 11-)
  local build_fingerprint=$(cat ${source}/*.info.txt | grep "Build Fingerprint:" | cut -c 20-)
  local build_description=$(cat ${source}/*.info.txt | grep "Version when read from CPV:" | cut -c 29-)
  local security_patch=$(python3 ${avbtool} info_image --image ${source}/vbmeta.img | grep "com.android.build.vendor.security_patch" | cut -c 54- | sed s/\'//g)
  local rollback_index=$(python3 ${avbtool} info_image --image ${source}/vbmeta.img | grep "Rollback Index:" | cut -c 27-)

  echo "Bootloader version:    $bootloader_version"
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

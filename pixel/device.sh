#!/bin/bash

# SPDX-FileCopyrightText: 2022-2023 The Calyx Institute
#
# SPDX-License-Identifier: Apache-2.0

#
# device:
#
#   Do it all for one device
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

device() {
  local device="${1}"
  source "${vars_path}/${device}"

  if [[ "$os_branch" == "lineage-19.1" || "$os_branch" == "lineage-20.0" || "$os_branch" == "lineage-21.0" ]]; then
    local factory_dir="${work_dir}/${device}/${build_id}/factory/${device}-${build_id,,}"

    "${script_path}/download.sh" "${device}"
    "${script_path}/extract-factory-image.sh" "${device}"

    pushd "${top}"
    device/google/${device}/extract-files.sh "${factory_dir}"
    popd

    if [[ "$os_branch" == "lineage-19.1" || "$os_branch" == "lineage-20.0" ]]; then
      "${script_path}/firmware.sh" "${device}"
    fi
  else
    local factory_zip="${work_dir}/${device}/${build_id}/$(basename ${image_url})"
    local extract_args="${factory_zip}"

    if [ ! -f "${factory_zip}" ]; then
      "${script_path}/download.sh" "${device}"
    fi

    if [ "$KEEP_DUMP" == "true" ] || [ "$KEEP_DUMP" == "1" ]; then
      extract_args+=" --keep-dump"
    fi

    extract_args+=" --regenerate --extract-factory"

    pushd "${top}"
    device/google/${device}/extract-files.py "${extract_args}"
    popd
  fi
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
    device "${1}"
  else
    error_m
  fi
}

### RUN PROGRAM ###

main "${@}"


##

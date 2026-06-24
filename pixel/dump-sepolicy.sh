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

decompile_cil() {
  local device="${1}"
  source "${vars_path}/${device}"

  local dev_dir="${work_dir}/dev/${device}"
  local download_dir="${work_dir}/${device}/${build_id}"
  local factory_dir="${download_dir}/$(basename ${image_url} .zip)"

  pushd "${top}" > /dev/null

  if [ -d "${dev_dir}/sepolicy" ]; then
    rm -rf "${dev_dir}/sepolicy"
  fi

  lineage/scripts/dev/decompile_cil.py \
      --current \
      --dump "${factory_dir}" \
      --extra-macros hardware/google/pixel-sepolicy/common/vendor \
      --cleanup-rules hardware/google/pixel-sepolicy/ignored/product \
      --cleanup-rules hardware/google/pixel-sepolicy/ignored/system_ext \
      --cleanup-rules hardware/google/pixel-sepolicy/ignored/vendor \
      --cleanup-rules hardware/google/pixel-sepolicy/common/system_ext \
      --cleanup-rules hardware/google/pixel-sepolicy/common/vendor \
      --cleanup-rules hardware/google/pixel-sepolicy/flipendo \
      --cleanup-rules hardware/google/pixel-sepolicy/googlebattery \
      --cleanup-rules hardware/google/pixel-sepolicy/hardware_info_app \
      --cleanup-rules hardware/google/pixel-sepolicy/logger_app \
      --cleanup-rules hardware/google/pixel-sepolicy/mm/gki \
      --cleanup-rules hardware/google/pixel-sepolicy/pixelstats \
      --cleanup-rules hardware/google/pixel-sepolicy/pixelsystemservice \
      --cleanup-rules hardware/google/pixel-sepolicy/power-libperfmgr \
      --cleanup-rules hardware/google/pixel-sepolicy/powerstats \
      --cleanup-rules hardware/google/pixel-sepolicy/rebalance_interrupts \
      --cleanup-rules hardware/google/pixel-sepolicy/turbo_adapter/vendor \
      --cleanup-rules hardware/google/pixel-sepolicy/vibrator/common \
      --cleanup-rules hardware/google/pixel-sepolicy/vibrator/cs40l25 \
      --cleanup-rules hardware/google/pixel-sepolicy/vibrator/cs40l26 \
      --cleanup-rules hardware/google/pixel-sepolicy/wifi_ext \
      --cleanup-rules hardware/google/pixel-sepolicy/wifi_perf_diag \
      --cleanup-rules hardware/google/pixel-sepolicy/wifi_sniffer \
      --output "${dev_dir}/sepolicy"

  popd > /dev/null
}
export -f decompile_cil

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
    parallel --line-buffer --tag decompile_cil ::: "${@}"
  fi
}

### RUN PROGRAM ###

main "${@}"


##

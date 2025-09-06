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
  if [ -d "${dev_dir}/sepolicy" ]; then
    rm -r "${dev_dir}/sepolicy"
  fi
  lineage/scripts/dev/decompile_cil.py \
      --current \
      --selinux "${factory_dir}/system_ext/etc/selinux" \
      --extra-rules device/google/gs-common/sepolicy/ignored/system_ext \
      --extra-rules hardware/google/pixel-sepolicy/common/system_ext \
      --extra-rules hardware/google/pixel-sepolicy/flipendo \
      --output "${dev_dir}/sepolicy/system_ext"
  lineage/scripts/dev/decompile_cil.py \
      --current \
      --selinux "${factory_dir}/product/etc/selinux" \
      --extra-rules device/google/gs-common/sepolicy/ignored/product \
      --output "${dev_dir}/sepolicy/product"
  lineage/scripts/dev/decompile_cil.py \
      --current \
      --selinux "${factory_dir}/vendor/etc/selinux" \
      --extra-macros hardware/google/pixel-sepolicy/common/vendor \
      --extra-rules device/google/gs-common/sepolicy/ignored/vendor \
      --extra-rules hardware/google/pixel-sepolicy/common/vendor \
      --extra-rules hardware/google/pixel-sepolicy/googlebattery \
      --extra-rules hardware/google/pixel-sepolicy/hardware_info_app \
      --extra-rules hardware/google/pixel-sepolicy/input \
      --extra-rules hardware/google/pixel-sepolicy/logger_app \
      --extra-rules hardware/google/pixel-sepolicy/mm/gki \
      --extra-rules hardware/google/pixel-sepolicy/pixelstats \
      --extra-rules hardware/google/pixel-sepolicy/pixelsystemservice \
      --extra-rules hardware/google/pixel-sepolicy/power-libperfmgr \
      --extra-rules hardware/google/pixel-sepolicy/powerstats \
      --extra-rules hardware/google/pixel-sepolicy/rebalance_interrupts \
      --extra-rules hardware/google/pixel-sepolicy/turbo_adapter/vendor \
      --extra-rules hardware/google/pixel-sepolicy/vibrator/common \
      --extra-rules hardware/google/pixel-sepolicy/vibrator/cs40l25 \
      --extra-rules hardware/google/pixel-sepolicy/vibrator/cs40l26 \
      --extra-rules hardware/google/pixel-sepolicy/wifi_ext \
      --extra-rules hardware/google/pixel-sepolicy/wifi_perf_diag \
      --extra-rules hardware/google/pixel-sepolicy/wifi_sniffer \
      --output "${dev_dir}/sepolicy/vendor"
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

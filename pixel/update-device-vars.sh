#!/bin/bash

# SPDX-FileCopyrightText: 2022 The Calyx Institute
#
# SPDX-License-Identifier: Apache-2.0

#
# update-vars:
#
#   Update Pixel device-specific variables by parsing Google's pages
#
#
##############################################################################


### SET ###

# use bash strict mode
set -euo pipefail


### TRAPS ###

# trap signals for clean exit
trap 'rm -rf ${tmp_dir} && exit $?' EXIT
trap 'error_m interrupted!' SIGINT

### CONSTANTS ###
readonly script_path="$(cd "$(dirname "$0")";pwd -P)"
readonly vars_path="${script_path}/../../../vendor/lineage/vars"

readonly tmp_dir="${TMPDIR:-/tmp}/pixel"

source "${vars_path}/pixels"
source "${vars_path}/common"

## HELP MESSAGE (USAGE INFO)
# TODO

### FUNCTIONS ###



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
  mkdir -p "${tmp_dir}"
  if [[ $# -ne 0 ]]; then
    ds=("${@}")
  else
    ds=("${devices[@]}")
  fi

  declare -a tmps
  declare -a build_ids
  for d in "${ds[@]}"; do
    local tmp=$(mktemp "${tmp_dir}/${d}.XXXXXXXXXX")
    tmps+=("$tmp")

    # Variables are marked readonly, do this to avoid it
    build_id=$(
      local dv="${vars_path}/${d}"
      source "${dv}"
      echo "${build_id}"
    )
    build_ids+=("${build_id}")
  done

  ${script_path}/get-new-device-vars.py --devices "${ds[@]}" --build-ids "${build_ids[@]}" --tmps "${tmps[@]}"

  for i in "${!ds[@]}"; do
    d="${ds[$i]}"
    tmp="${tmps[$i]}"
    (
      local dv="${vars_path}/${d}"
      source "${dv}"
      source "${tmp}"
      sed -i "/ build_number=/c\readonly build_number=\"$new_build_number\"" "${dv}"
      sed -i "/ image_url=/c\readonly image_url=\"$new_image_url\"" "${dv}"
      sed -i "/ image_sha256=/c\readonly image_sha256=\"$new_image_sha256\"" "${dv}"
      sed -i "/ flash_url=/c\readonly flash_url=\"$new_flash_url\"" "${dv}"
      sed -i "/ ota_url=/c\readonly ota_url=\"$new_ota_url\"" "${dv}"
      sed -i "/ ota_sha256=/c\readonly ota_sha256=\"$new_ota_sha256\"" "${dv}"
    )
  done
}

### RUN PROGRAM ###

main "${@}"


##

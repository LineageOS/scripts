#!/bin/bash

# SPDX-FileCopyrightText: 2022 The Calyx Institute
#
# SPDX-License-Identifier: Apache-2.0

#
# dev:
#
#   Dump overlays and sepolicy for all devices
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

## HELP MESSAGE (USAGE INFO)
# TODO

### FUNCTIONS ###

device() {
  local cmd="${1}"
  local device="${2}"
  local script_path="${3}"

  case "${cmd}" in
    overlay) "${script_path}/dump-rro.sh" "${device}" ;;
    sepolicy) "${script_path}/dump-sepolicy.sh" "${device}" ;;
    *) error_m "Invalid command: ${cmd}. Use 'overlay' or 'sepolicy'." ;;
  esac
}

export -f device

# error message
# ARG1: error message for STDERR
# ARG2: error status
error_m() {
  echo "ERROR: ${1:-'failed.'}" 1>&2
  return "${2:-1}"
}

export -f error_m

# print help message.
help_message() {
  echo "${help_message:-'No help available.'}"
}

main() {
  if [[ $# -lt 1 ]]; then
    echo "Usage: $0 [overlay|sepolicy] [devices...]"
    exit 1
  fi

  local cmd="${1}"
  shift

  if [[ $# -ne 0 ]] ; then
    parallel --line-buffer --tag device ::: "${cmd}" ::: "${@}" ::: "${script_path}"
  else
    parallel --line-buffer --tag device ::: "${cmd}" ::: "${devices[@]}" ::: "${script_path}"
  fi
}

### RUN PROGRAM ###

main "${@}"


##

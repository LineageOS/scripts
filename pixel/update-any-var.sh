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
trap 'error_m interrupted!' SIGINT

### CONSTANTS ###
readonly script_path="$(cd "$(dirname "$0")";pwd -P)"
readonly vars_path="${script_path}/../../../vendor/lineage/vars"

source "${vars_path}/pixels"

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
  local key="${1}"
  local value="${2}"
  shift; shift
  if [[ $# -ne 0 ]]; then
    local files="${@}"
  else
    local files="${devices[@]}"
  fi

  for f in ${files}; do
    (
      local fv="${vars_path}/${f}"
      source "${fv}"
      sed -i "/ prev_${key}=/c\readonly prev_${key}=\"${!key}\"" "${fv}"
      sed -i "/ ${key}=/c\readonly ${key}=\"$value\"" "${fv}"
    )
  done
}

### RUN PROGRAM ###

main "${@}"


##

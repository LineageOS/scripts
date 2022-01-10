#!/bin/bash
#
# SPDX-FileCopyrightText: 2022 The Calyx Institute
#
# SPDX-License-Identifier: Apache-2.0
#
# merge-aosp:
#
#   Merge the latest AOSP release based on variables
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
readonly vars_path="${script_path}/../vars"

source "${vars_path}/common"

## HELP MESSAGE (USAGE INFO)
# TODO

### FUNCTIONS ###

merge_aosp_forks() {
  "${script_path}"/merge-aosp-forks.sh merge "${prev_aosp_tag}" "${aosp_tag}"
}

squash_aosp_merge() {
  "${script_path}"/squash.sh merge "${prev_aosp_tag}" "${aosp_tag}"
}

upload_squash_to_review() {
  "${script_path}"/upload-squash.sh merge "${prev_aosp_tag}" "${aosp_tag}"
}

push_merge() {
  "${script_path}"/push-merge.sh merge "${prev_aosp_tag}" "${aosp_tag}"
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
  merge_aosp_forks
  read -p "Waiting for conflict resolution before squashing. Press enter when done."
  read -p "Once more, just to be safe"
  squash_aosp_merge
  upload_squash_to_review
  echo "Don't forget to update the manifest!"
}

### RUN PROGRAM ###

main "${@}"


##

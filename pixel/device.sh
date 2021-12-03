#!/bin/bash
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
readonly vars_path="${script_path}/../vars/"
readonly top="${script_path}/../../../"

readonly work_dir="${WORK_DIR:-/tmp/pixel}"

source "${vars_path}/devices"

## HELP MESSAGE (USAGE INFO)
# TODO

### FUNCTIONS ###

device() {
  local device="${1}"
  source "${vars_path}/${device}"
  local factory_dir="${work_dir}/${device}/${build_id}/factory/${device}-${build_id,,}"

  "${script_path}/download.sh" "${device}"
  "${script_path}/extract-factory-image.sh" "${device}"

  pushd "${top}"
  device/google/${device}/extract-files.sh "${factory_dir}/image"
  popd

  "${script_path}/firmware.sh" "${device}"
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

#!/bin/bash
#
# extract:
#
#   Extract Pixel factory images
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

readonly work_dir="${WORK_DIR:-/tmp/pixel}"

source "${vars_path}/devices"

readonly device="${1}"
source "${vars_path}/${device}"

## HELP MESSAGE (USAGE INFO)
# TODO

### FUNCTIONS ###

extract_factory_image() {
  local factory_dir="${work_dir}/${device}/${build_id}/factory"
  mkdir -p "${factory_dir}"
  local factory_zip="${work_dir}/${device}/${build_id}/$(basename ${image_url})"
  echo "${image_sha256} ${factory_zip}" | sha256sum --check --status
  pushd "${factory_dir}"
  unzip -o "${factory_zip}"
  pushd ${device}-${build_id,,}
  unzip -o "image-${device}-${build_id,,}.zip" -d "image"
  popd
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
  extract_factory_image
}

### RUN PROGRAM ###

main "${@}"


##

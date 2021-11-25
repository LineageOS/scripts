#!/bin/bash
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
readonly vars_path="${script_path}/../vars/"

readonly tmp_dir="${TMPDIR:-/tmp}/pixel"

source "${vars_path}/devices"

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
    local ds="${@}"
  else
    local ds="${devices[@]}"
  fi

  for d in ${ds}; do
    (
      local tmp=$(mktemp "${tmp_dir}/${d}.XXXXXXXXXX")
      local dv="${vars_path}/${d}"
      source "${dv}"
      ${script_path}/get-new-device-vars.py -b "${build_id}" -d "${d}"> "${tmp}"
      source "${tmp}"
      if [[ "${new_aosp_tag}" != "${aosp_tag}" ]]; then
        sed -i "/ prev_aosp_tag=/c\readonly prev_aosp_tag=\"$aosp_tag\"" "${dv}"
        sed -i "/ aosp_tag=/c\readonly aosp_tag=\"$new_aosp_tag\"" "${dv}"
      fi
      sed -i "/ image_url=/c\readonly image_url=\"$new_image_url\"" "${dv}"
      sed -i "/ image_sha256=/c\readonly image_sha256=\"$new_image_sha256\"" "${dv}"
      sed -i "/ flash_url=/c\readonly flash_url=\"$new_flash_url\"" "${dv}"
      sed -i "/ ota_url=/c\readonly ota_url=\"$new_ota_url\"" "${dv}"
      sed -i "/ ota_sha256=/c\readonly ota_sha256=\"$new_ota_sha256\"" "${dv}"
      sed -i "/ security_patch=/c\readonly security_patch=\"$new_security_patch\"" "${dv}"
    )
  done
}

### RUN PROGRAM ###

main "${@}"


##

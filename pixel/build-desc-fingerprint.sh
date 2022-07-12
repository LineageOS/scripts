#!/bin/bash
#
# build-desc-fingerprint:
#
#   Update build.prop build description and fingerprint overrides to match stock
#
#
##############################################################################


### SET ###

# use bash strict mode
set -euo pipefail
set -x

### TRAPS ###

# trap signals for clean exit
trap 'rm -rf ${tmp_dir} && exit $?' EXIT
trap 'error_m interrupted!' SIGINT

### CONSTANTS ###
readonly script_path="$(cd "$(dirname "$0")";pwd -P)"
readonly vars_path="${script_path}/../../../vendor/lineage/vars"
readonly top="${script_path}/../../.."

readonly tmp_dir="${TMPDIR:-/tmp}/pixel"

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
  mkdir -p "${tmp_dir}"
  if [[ $# -ne 0 ]]; then
    local ds="${@}"
  else
    local ds="${devices[@]}"
  fi

  for d in ${ds}; do
    (
      local dv="${vars_path}/${d}"
      source "${dv}"
      local mk="$(ls ${top}/device/google/*/lineage_${d}.mk)"
      sed -i "s/${prev_build_id}/${build_id}/g" "${mk}"
      sed -i "s/${prev_build_number}/${build_number}/g" "${mk}"
      cd "${top}/device/google/${d}"
      git commit -a -m "Update fingerprint/build description from ${build_id}"
      cd ../../..
    )
  done
}

### RUN PROGRAM ###

main "${@}"


##

#!/bin/bash

# SPDX-FileCopyrightText: 2022 The Calyx Institute
#
# SPDX-License-Identifier: Apache-2.0

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


### TRAPS ###

# trap signals for clean exit
trap 'error_m interrupted!' SIGINT

### CONSTANTS ###
readonly script_path="$(cd "$(dirname "$0")";pwd -P)"
readonly vars_path="${script_path}/../../../vendor/lineage/vars"
readonly top="${script_path}/../../.."

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
  if [[ $# -ne 0 ]]; then
    local ds="${@}"
  else
    local ds="${devices[@]}"
  fi

  # Update the makefiles
  for d in ${ds}; do
    (
      local dv="${vars_path}/${d}"
      source "${dv}"
      local mk="$(ls ${top}/device/google/*/lineage_${d}.mk)"
      desc="${d}-user ${android_version} ${build_id} ${build_number} release-keys"
      fingerprint="google/${d}/${d}:${android_version}/${build_id}/${build_number}:user/release-keys"
      sed -i "/BuildDesc/c\    BuildDesc=\"${desc}\" \\\\" "${mk}"
      sed -i "/BuildFingerprint/c\    BuildFingerprint=${fingerprint} \\\\" "${mk}"
    )
  done

  # Commit the changes
  for d in ${ds}; do
    (
      local dv="${vars_path}/${d}"
      source "${dv}"
      local dir="$(ls ${top}/device/google/*/lineage_${d}.mk | sed s#/lineage_${d}.mk##)"
      cd "${dir}"
      if [[ -n "$(git status --porcelain)" ]]; then
        git commit -a -m "Update fingerprint/build description from ${build_id}"
      fi
    )
  done
}

### RUN PROGRAM ###

main "${@}"


##

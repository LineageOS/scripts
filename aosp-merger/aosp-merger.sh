#!/bin/bash
#
# SPDX-FileCopyrightText: 2022 The Calyx Institute
# SPDX-FileCopyrightText: 2022 The LineageOS Project
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
readonly vars_path="${script_path}/../../../vendor/lineage/vars"

source "${vars_path}/common"
source "${vars_path}/pixels"
source "${vars_path}/kernel_repos"
source "${vars_path}/qcom"

TOP="${script_path}/../../.."

# make sure we have consistent and readable commit messages
export LC_MESSAGES=C
export LC_TIME=C

## HELP MESSAGE (USAGE INFO)
# TODO

### FUNCTIONS ###

# Reverse merge AOSP to AOSP (for testing only)
merge_aosp() {
  "${script_path}"/merge-aosp.sh --old-tag "${common_aosp_tag}" --new-tag "${prev_common_aosp_tag}" --branch-suffix "${common_aosp_tag}_merge-${prev_common_aosp_tag}"
}

# Merge AOSP to forks
merge_aosp_forks() {
  "${script_path}"/merge-aosp-forks.sh --old-tag "${prev_common_aosp_tag}" --new-tag "${common_aosp_tag}" --branch-suffix "${os_branch}_merge-${common_aosp_tag}"
}

squash_aosp_merge() {
  "${script_path}"/squash.sh --branch-suffix "${os_branch}_merge-${common_aosp_tag}"
}

upload_squash_aosp_to_review() {
  "${script_path}"/upload-squash.sh --branch-suffix "${os_branch}_merge-${common_aosp_tag}"
}

push_aosp_merge() {
  "${script_path}"/push-merge.sh --branch-suffix "${os_branch}_merge-${common_aosp_tag}"
}

# Merge AOSP to pixel device forks
merge_pixel_device() {
  for repo in ${device_repos[@]}; do
    "${script_path}"/_subtree_merge_helper.sh --project-path "${repo}" --old-tag "${prev_aosp_tag}" --new-tag "${aosp_tag}" --branch-suffix "${os_branch}_merge-${aosp_tag}"
  done
}

squash_pixel_device() {
  "${script_path}"/squash.sh --new-tag "${aosp_tag}" --branch-suffix "${os_branch}_merge-${aosp_tag}" --pixel
}

upload_squash_device_to_review() {
  "${script_path}"/upload-squash.sh --branch-suffix "${os_branch}_merge-${aosp_tag}" --pixel
}

push_device_merge() {
  "${script_path}"/push-merge.sh --branch-suffix "${os_branch}_merge-${aosp_tag}"
}

# Merge AOSP to pixel kernel forks
merge_pixel_kernel() {
  for repo in ${device_kernel_repos}; do
    "${script_path}"/_subtree_merge_helper.sh --project-path "${repo}" --old-tag "${prev_kernel_tag}" --new-tag "${kernel_tag}" --branch-suffix "${os_branch}_merge-${kernel_tag}"
  done
}

squash_pixel_kernel() {
  "${script_path}"/squash.sh --new-tag "${kernel_tag}" --branch-suffix "${os_branch}_merge-${kernel_tag}" --pixel
}

upload_squash_kernel_to_review() {
  "${script_path}"/upload-squash.sh --branch-suffix "${os_branch}_merge-${kernel_tag}" --pixel
}

push_kernel_merge() {
  "${script_path}"/push-merge.sh --branch-suffix "${os_branch}_merge-${kernel_tag}"
}

# Merge CLO to forks
merge_clo() {
  "${script_path}"/_merge_helper.sh --project-path "${repo}" --new-tag "${1}" --branch-suffix "${os_branch}_merge-${1}"
}

squash_clo_merge() {
  "${script_path}"/squash.sh --new-tag "${1}" --branch-suffix "${os_branch}_merge-${1}"
}

upload_squash_clo_to_review() {
  "${script_path}"/upload-squash.sh --new-tag "${1}" --branch-suffix "${os_branch}_merge-${1}"
}

push_clo_merge() {
  "${script_path}"/push-merge.sh --branch-suffix "${os_branch}_merge-${1}"
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
  if [ "$#" -eq 0 ]; then
    export MERGEDREPOS="${TOP}/merged_repos.txt"
    # Remove any existing list of merged repos file
    rm -f "${MERGEDREPOS}"

    merge_aosp_forks
    # Run this to print list of conflicting repos
    cat "${MERGEDREPOS}" | grep -w conflict-merge || true
    read -p "Waiting for conflict resolution before squashing. Press enter when done."
    read -p "Once more, just to be safe"
    squash_aosp_merge
    upload_squash_aosp_to_review
    echo "Don't forget to update the manifest!"

    unset MERGEDREPOS
  elif [ "${1}" = "aosp" ]; then
    export MERGEDREPOS="${TOP}/merged_repos_aosp.txt"
    # Remove any existing list of merged repos file
    rm -f "${MERGEDREPOS}"

    merge_aosp

    unset MERGEDREPOS
  elif [ "${1}" = "devices" ]; then
    for device in ${devices[@]}; do
      (
      source "${vars_path}/${device}"
      export MERGEDREPOS="${TOP}/merged_repos_${device}.txt"
      # Remove any existing list of merged repos file
      rm -f "${MERGEDREPOS}"

      merge_pixel_device
      # Run this to print list of conflicting repos
      cat "${MERGEDREPOS}" | grep -w conflict-merge || true
      read -p "Waiting for conflict resolution before squashing. Press enter when done."
      read -p "Once more, just to be safe"
      squash_pixel_device
      upload_squash_device_to_review

      unset MERGEDREPOS
      )
    done
  elif [ "${1}" = "kernels" ]; then
    for kernel in ${kernel_repos[@]}; do
      (
      source "${vars_path}/${kernel}"

      readonly device_kernel_repos="kernel/google/${kernel}"

      export MERGEDREPOS="${TOP}/merged_repos_${kernel}_kernel.txt"
      # Remove any existing list of merged repos file
      rm -f "${MERGEDREPOS}"

      merge_pixel_kernel
      # Run this to print list of conflicting repos
      cat "${MERGEDREPOS}" | grep -w conflict-merge || true
      read -p "Waiting for conflict resolution before squashing. Press enter when done."
      read -p "Once more, just to be safe"
      squash_pixel_kernel
      upload_squash_kernel_to_review

      unset MERGEDREPOS
      )
    done
  elif [ "${1}" = "clo" ]; then
    for repo in $(repo list -p -g ${2}); do
      (
      qcom_tag="${qcom_group_revision[${2}]}"

      export MERGEDREPOS="${TOP}/merged_repos_clo_${2}.txt"
      # Remove any existing list of merged repos file
      rm -f "${MERGEDREPOS}"

      merge_clo "${qcom_tag}"
      # Run this to print list of conflicting repos
      cat "${MERGEDREPOS}" | grep -w conflict-merge || true
      read -p "Waiting for conflict resolution before squashing. Press enter when done."
      read -p "Once more, just to be safe"
      squash_clo_merge "${qcom_tag}"
      upload_squash_clo_to_review "${qcom_tag}"

      unset MERGEDREPOS
      )
    done
  elif [ "${1}" = "submit-platform" ]; then
    export MERGEDREPOS="${TOP}/merged_repos.txt"

    push_aosp_merge

    unset MERGEDREPOS
  elif [ "${1}" = "submit-devices" ]; then
    for device in ${devices[@]}; do
      (
      source "${vars_path}/${device}"
      export MERGEDREPOS="${TOP}/merged_repos_${device}.txt"

      push_device_merge

      unset MERGEDREPOS
      )
    done
  elif [ "${1}" = "submit-kernels" ]; then
    for kernel in ${kernel_repos[@]}; do
      (
      source "${vars_path}/${kernel}"
      export MERGEDREPOS="${TOP}/merged_repos_${kernel}_kernel.txt"

      push_kernel_merge

      unset MERGEDREPOS
      )
    done
  elif [ "${1}" = "submit-clo" ]; then
    for repo in $(repo list -p -g ${2}); do
      (
      qcom_tag="${qcom_group_revision[${2}]}"

      export MERGEDREPOS="${TOP}/merged_repos_clo_${group}.txt"

      push_clo_merge "${qcom_tag}"

      unset MERGEDREPOS
      )
    done
  fi
}

### RUN PROGRAM ###

main "${@}"


##

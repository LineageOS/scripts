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

# export everything that parallel needs
export TOP script_path vars_path merge_method common_aosp_tag prev_common_aosp_tag os_branch device_branch

## HELP MESSAGE (USAGE INFO)
# TODO

### FUNCTIONS ###

# Reverse merge AOSP to AOSP (for testing only)
merge_aosp() {
  "${script_path}"/merge-aosp.sh --old-tag "${common_aosp_tag}" --new-tag "${prev_common_aosp_tag}" --branch-suffix "${common_aosp_tag}_merge-${prev_common_aosp_tag}"
}
export -f merge_aosp

# Merge AOSP to forks
merge_aosp_forks() {
  "${script_path}"/merge-aosp-forks.sh --old-tag "${prev_common_aosp_tag}" --new-tag "${common_aosp_tag}" --branch-suffix "${os_branch}_merge-${common_aosp_tag}"
}
export -f merge_aosp_forks

post_aosp_merge() {
  if [ "${merge_method}" = "merge" ]; then
    return
  else
    "${script_path}"/squash.sh --branch-suffix "${os_branch}_merge-${common_aosp_tag}"
  fi
}
export -f post_aosp_merge

upload_aosp_merge_to_review() {
  if [ "${merge_method}" = "merge" ]; then
    "${script_path}"/upload-merge.sh --branch-suffix "${os_branch}_merge-${common_aosp_tag}"
  else
    "${script_path}"/upload-squash.sh --branch-suffix "${os_branch}_merge-${common_aosp_tag}"
  fi
}
export -f upload_aosp_merge_to_review

push_aosp_merge() {
  "${script_path}"/push-merge.sh --branch-suffix "${os_branch}_merge-${common_aosp_tag}"
}
export -f push_aosp_merge

# Merge AOSP to pixel device forks
merge_pixel_device() {
  source "${vars_path}/${1}"
  for repo in ${device_repos[@]}; do
    "${script_path}"/_subtree_merge_helper.sh --project-path "${repo}" --old-tag "${prev_aosp_tag}" --new-tag "${aosp_tag}" --branch-suffix "${device_branch}_merge-${aosp_tag}"
  done
}
export -f merge_pixel_device

post_pixel_device_merge() {
  source "${vars_path}/${1}"
  if [ "${merge_method}" = "merge" ]; then
    return
  else
    "${script_path}"/squash.sh --new-tag "${aosp_tag}" --branch-suffix "${device_branch}_merge-${aosp_tag}" --pixel
  fi
}
export -f post_pixel_device_merge

upload_pixel_device_to_review() {
  source "${vars_path}/${1}"
  if [ "${merge_method}" = "merge" ]; then
    "${script_path}"/upload-merge.sh --branch-suffix "${device_branch}_merge-${aosp_tag}" --pixel
  else
    "${script_path}"/upload-squash.sh --branch-suffix "${device_branch}_merge-${aosp_tag}" --pixel
  fi
}
export -f upload_pixel_device_to_review

push_device_merge() {
  source "${vars_path}/${1}"
  "${script_path}"/push-merge.sh --branch-suffix "${device_branch}_merge-${aosp_tag}" --pixel
}
export -f push_device_merge

# Merge AOSP to pixel kernel forks
merge_pixel_kernel() {
  source "${vars_path}/${1}"
  readonly kernel_short="$(echo ${1} | cut -d / -f 3)"
  source "${vars_path}/${kernel_short}"

  readonly device_kernel_repo="${1}"

  "${script_path}"/_subtree_merge_helper.sh --project-path "${device_kernel_repo}" --old-tag "${prev_kernel_tag}" --new-tag "${kernel_tag}" --branch-suffix "${device_branch}_merge-${kernel_tag}"
}
export -f merge_pixel_kernel

post_pixel_kernel_merge() {
  source "${vars_path}/${1}"
  if [ "${merge_method}" = "merge" ]; then
    return
  else
    "${script_path}"/squash.sh --new-tag "${kernel_tag}" --branch-suffix "${device_branch}_merge-${kernel_tag}" --pixel
  fi
}
export -f post_pixel_kernel_merge

upload_pixel_kernel_to_review() {
  source "${vars_path}/${1}"
  if [ "${merge_method}" = "merge" ]; then
    "${script_path}"/upload-merge.sh --branch-suffix "${device_branch}_merge-${kernel_tag}" --pixel
  else
    "${script_path}"/upload-squash.sh --branch-suffix "${device_branch}_merge-${kernel_tag}" --pixel
  fi
}
export -f upload_pixel_kernel_to_review

push_kernel_merge() {
  source "${vars_path}/${1}"
  "${script_path}"/push-merge.sh --branch-suffix "${device_branch}_merge-${kernel_tag}" --pixel
}
export -f push_kernel_merge

# Merge CLO to forks
merge_clo() {
  "${script_path}"/_merge_helper.sh --project-path "${2}" --new-tag "${1}" --branch-suffix "${os_branch}_merge-${1}"
}
export -f merge_clo

squash_clo_merge() {
  "${script_path}"/squash.sh --new-tag "${1}" --branch-suffix "${os_branch}_merge-${1}"
}
export -f squash_clo_merge

upload_squash_clo_to_review() {
  if [ "${merge_method}" = "merge" ]; then
    "${script_path}"/upload-merge.sh --new-tag "${1}" --branch-suffix "${os_branch}_merge-${1}"
  else
    "${script_path}"/upload-squash.sh --new-tag "${1}" --branch-suffix "${os_branch}_merge-${1}"
  fi
}
export -f upload_squash_clo_to_review

push_clo_merge() {
  "${script_path}"/push-merge.sh --branch-suffix "${os_branch}_merge-${1}"
}
export -f push_clo_merge

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
    read -p "Waiting for conflict resolution. Press enter when done."
    post_aosp_merge
    upload_aosp_merge_to_review
    echo "Don't forget to update the manifest!"

    unset MERGEDREPOS
  elif [ "${1}" = "aosp" ]; then
    export MERGEDREPOS="${TOP}/merged_repos_aosp.txt"
    # Remove any existing list of merged repos file
    rm -f "${MERGEDREPOS}"

    merge_aosp

    unset MERGEDREPOS
  elif [ "${1}" = "devices" ]; then
    export MERGEDREPOS="${TOP}/merged_repos_devices.txt"
    # Remove any existing list of merged repos file
    rm -f "${MERGEDREPOS}"

    parallel -j8 --line-buffer --tag merge_pixel_device ::: ${devices[@]}

    # Run this to print list of conflicting repos
    cat "${MERGEDREPOS}" | grep -w conflict-merge || true
    read -p "Waiting for conflict resolution. Press enter when done."

    parallel -j8 --line-buffer --tag 'post_pixel_device_merge; upload_pixel_device_to_review' ::: ${devices[@]}

    unset MERGEDREPOS
  elif [ "${1}" = "kernels" ]; then
    export MERGEDREPOS="${TOP}/merged_repos_kernels.txt"
    # Remove any existing list of merged repos file
    rm -f "${MERGEDREPOS}"

    parallel -j8 --line-buffer --tag merge_pixel_kernel ::: ${kernel_repos[@]}

    # Run this to print list of conflicting repos
    cat "${MERGEDREPOS}" | grep -w conflict-merge || true
    read -p "Waiting for conflict resolution. Press enter when done."

    parallel -j8 --line-buffer --tag 'post_pixel_kernel_merge; upload_pixel_kernel_to_review' ::: ${kernel_repos[@]}

    unset MERGEDREPOS
  elif [ "${1}" = "clo" ]; then
    qcom_tag="${qcom_group_revision[${2}]}"

    export MERGEDREPOS="${TOP}/merged_repos_clo_${2}.txt"
    # Remove any existing list of merged repos file
    rm -f "${MERGEDREPOS}"

    parallel -j8 --line-buffer --tag merge_clo "${qcom_tag}" ::: $(repo list -p -g ${2})

    # Run this to print list of conflicting repos
    cat "${MERGEDREPOS}" | grep -w conflict-merge || true
    read -p "Waiting for conflict resolution. Press enter when done."
    squash_clo_merge "${qcom_tag}"
    upload_squash_clo_to_review "${qcom_tag}"

    unset MERGEDREPOS
  elif [ "${1}" = "submit-platform" ]; then
    export MERGEDREPOS="${TOP}/merged_repos.txt"

    push_aosp_merge

    unset MERGEDREPOS
  elif [ "${1}" = "submit-devices" ]; then
    export MERGEDREPOS="${TOP}/merged_repos_devices.txt"

    parallel -j8 --line-buffer --tag push_device_merge ::: ${devices[@]}

    unset MERGEDREPOS
  elif [ "${1}" = "submit-kernels" ]; then
    export MERGEDREPOS="${TOP}/merged_repos_kernels.txt"

    parallel -j8 --line-buffer --tag push_kernel_merge ::: ${kernel_repos[@]}

    unset MERGEDREPOS
  elif [ "${1}" = "submit-clo" ]; then
    qcom_tag="${qcom_group_revision[${2}]}"

    export MERGEDREPOS="${TOP}/merged_repos_clo_${2}.txt"

    push_clo_merge "${qcom_tag}"

    unset MERGEDREPOS
  fi
}

### RUN PROGRAM ###

main "${@}"


##

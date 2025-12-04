#!/bin/bash
#
# SPDX-FileCopyrightText: 2017, 2020-2022 The LineageOS Project
# SPDX-FileCopyrightText: 2021-2023 The Calyx Institute
#
# SPDX-License-Identifier: Apache-2.0
#

usage() {
    echo "Usage ${0} -b <branch-suffix>"
}

# Verify argument count
if [ "${#}" -eq 0 ]; then
    usage
    exit 1
fi

while [ "${#}" -gt 0 ]; do
    case "${1}" in
        -b | --branch-suffix )
                BRANCHSUFFIX="${2}"; shift
                ;;
        * )
                usage
                exit 1
                ;;
    esac
    shift
done

### CONSTANTS ###
readonly script_path="$(cd "$(dirname "$0")";pwd -P)"
readonly vars_path="${script_path}/../../../vendor/lineage/vars"

source "${vars_path}/common"

TOP="${script_path}/../../.."
STAGINGBRANCH="staging/${BRANCHSUFFIX}"

# Source build environment (needed for lineageremote)
source "${TOP}/build/envsetup.sh"

# List of merged repos
PROJECTPATHS=$(cat ${MERGEDREPOS} | grep -w merge | awk '{printf "%s\n", $2}')

echo -e "\n#### Staging branch = ${STAGINGBRANCH} ####"

# Make sure manifest and forked repos are in a consistent state
echo -e "\n#### Verifying there are no uncommitted changes on forked AOSP projects ####"
for PROJECTPATH in ${PROJECTPATHS} .repo/manifests; do
    cd "${TOP}/${PROJECTPATH}"
    if [[ -n "$(git status --porcelain)" ]]; then
        echo "Path ${PROJECTPATH} has uncommitted changes. Please fix."
        exit 1
    fi
done
echo "#### Verification complete - no uncommitted changes found ####"

echo -e "\n#### $(basename ${MERGEDREPOS}) ####"
read -p "Pushing ${STAGINGBRANCH}. Press enter to confirm."

# Iterate over each forked project
for PROJECTPATH in ${PROJECTPATHS}; do
    cd "${TOP}/${PROJECTPATH}"

    BRANCH=$(git config --get branch.${STAGINGBRANCH}.merge | sed 's|refs/heads/||')
    if [ -z "${BRANCH}" ]; then
        BRANCH="${os_branch}"
    fi

    echo -e "\n#### Submitting ${PROJECTPATH} merge ####"
    git checkout "${STAGINGBRANCH}"
    lineageremote | grep -v "Remote 'lineage' created"
    git push lineage HEAD:refs/heads/"${BRANCH}"
done

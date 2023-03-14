#!/bin/bash
#
# SPDX-FileCopyrightText: 2017, 2020-2022 The LineageOS Project
# SPDX-FileCopyrightText: 2021-2022 The Calyx Institute
#
# SPDX-License-Identifier: Apache-2.0
#

usage() {
    echo "Usage ${0} -n <new-tag> -b <branch-suffix> --pixel"
}

# Verify argument count
if [ "${#}" -eq 0 ]; then
    usage
    exit 1
fi

PIXEL=false

while [ "${#}" -gt 0 ]; do
    case "${1}" in
        -n | --new-tag )
                NEWTAG="${2}"; shift
                ;;
        -b | --branch-suffix )
                BRANCHSUFFIX="${2}"; shift
                ;;
        -p | --pixel )
                PIXEL=true; shift
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
if [ ! -z "${NEWTAG}" ]; then
    TOPIC="${NEWTAG}"
elif [ "${PIXEL}" = true ]; then
    TOPIC="${topic}_pixel"
else
    TOPIC="${topic}"
fi

# Source build environment (needed for lineageremote)
source "${TOP}/build/envsetup.sh"

# List of merged repos
PROJECTPATHS=$(cat ${MERGEDREPOS} | grep -w merge | awk '{printf "%s\n", $2}')

echo "#### Staging branch = ${STAGINGBRANCH} ####"

# Make sure manifest and forked repos are in a consistent state
echo "#### Verifying there are no uncommitted changes on forked AOSP projects ####"
for PROJECTPATH in ${PROJECTPATHS} .repo/manifests; do
    cd "${TOP}/${PROJECTPATH}"
    if [[ -n "$(git status --porcelain)" ]]; then
        echo "Path ${PROJECTPATH} has uncommitted changes. Please fix."
        exit 1
    fi
done
echo "#### Verification complete - no uncommitted changes found ####"

# Iterate over each forked project
for PROJECTPATH in ${PROJECTPATHS}; do
    cd "${TOP}/${PROJECTPATH}"

    if [ "${PIXEL}" = true ]; then
        BRANCH="${device_branch}"
    else
        BRANCH=$(git config --get branch.${STAGINGBRANCH}.merge | sed 's|refs/heads/||')
        if [ -z "${BRANCH}" ]; then
            BRANCH="${os_branch}"
        fi
    fi

    echo "#### Pushing ${PROJECTPATH} merge to review ####"
    git checkout "${STAGINGBRANCH}"
    lineageremote | grep -v "Remote 'lineage' created"
    FIRST_SHA="$(git show -s --pretty=%P HEAD | cut -d ' ' -f 1)"
    SECOND_SHA="$(git show -s --pretty=%P HEAD | cut -d ' ' -f 2)"
    git push lineage HEAD:refs/for/"${BRANCH}"%base="${FIRST_SHA}",base="${SECOND_SHA}",topic="${TOPIC}"
done

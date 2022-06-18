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
BRANCH="${lineageos_branch}"
STAGINGBRANCH="staging/${BRANCHSUFFIX}"
SQUASHBRANCH="squash/${BRANCHSUFFIX}"

# List of merged repos
PROJECTPATHS=$(cat ${MERGEDREPOS} | grep -w merge | awk '{printf "%s\n", $2}')

echo "#### Branch = ${BRANCH} Squash branch = ${SQUASHBRANCH} ####"

# Make sure manifest and forked repos are in a consistent state
echo "#### Verifying there are no uncommitted changes on LineageOS forked AOSP projects ####"
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
    echo "#### Squashing ${PROJECTPATH} ####"
    repo abandon "${SQUASHBRANCH}" .
    git checkout -b "${SQUASHBRANCH}" "${STAGINGBRANCH}"
    git branch --set-upstream-to=m/"${BRANCH}"
    git reset --soft m/"${BRANCH}"
    git add .
    if [ "${PIXEL}" = true ]; then
        git commit -m "[SQUASH] Merge tag '${NEWTAG}' into ${STAGINGBRANCH}" -m "$(cat .git/CHANGE_ID)"
        rm .git/CHANGE_ID
    else
        git commit -m "[SQUASH] $(git log ${STAGINGBRANCH} -1 --pretty=%s)" -m "$(git log ${STAGINGBRANCH} -1 --pretty=%b)"
    fi
done

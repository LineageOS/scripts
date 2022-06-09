#!/bin/bash
#
# Copyright (C) 2017, 2020-2021 The LineageOS Project
# Copyright (C) 2021-2022 The Calyx Institute
#
# SPDX-License-Identifier: Apache-2.0
#

usage() {
    echo "Usage ${0} <merge|rebase> <oldaosptag> <newaosptag> <pixel>"
}

# Verify argument count
if [ "$#" -ne 4 ]; then
    usage
    exit 1
fi

OPERATION="${1}"
OLDTAG="${2}"
NEWTAG="${3}"
PIXEL="${4}"

if [ "${OPERATION}" != "merge" -a "${OPERATION}" != "rebase" ]; then
    usage
    exit 1
fi

### CONSTANTS ###
readonly script_path="$(cd "$(dirname "$0")";pwd -P)"
readonly vars_path="${script_path}/../../../vendor/lineage/vars"

source "${vars_path}/common"

TOP="${script_path}/../../.."
BRANCH="${lineageos_branch}"
STAGINGBRANCH="staging/${BRANCH}_${OPERATION}-${NEWTAG}"
SQUASHBRANCH="squash/${BRANCH}_${OPERATION}-${NEWTAG}"

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
    if [[ -z "${PIXEL}" ]]; then
        git commit -m "[SQUASH] $(git log ${STAGINGBRANCH} -1 --pretty=%s)" -m "$(git log ${STAGINGBRANCH} -1 --pretty=%b)"
    else
        git commit -m "[SQUASH] Merge tag '${NEWTAG}' into ${STAGINGBRANCH}"
    fi
done

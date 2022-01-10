#!/bin/bash
#
# SPDX-FileCopyrightText: 2017, 2020-2022 The LineageOS Project
# SPDX-FileCopyrightText: 2021-2022 The Calyx Institute
#
# SPDX-License-Identifier: Apache-2.0
#

usage() {
    echo "Usage ${0} <merge|rebase> <oldaosptag> <newaosptag>"
}

# Verify argument count
if [ "$#" -ne 3 ]; then
    usage
    exit 1
fi

OPERATION="${1}"
OLDTAG="${2}"
NEWTAG="${3}"

if [ "${OPERATION}" != "merge" -a "${OPERATION}" != "rebase" ]; then
    usage
    exit 1
fi

### CONSTANTS ###
readonly script_path="$(cd "$(dirname "$0")";pwd -P)"
readonly vars_path="${script_path}/../vars"

source "${vars_path}/common"

TOP="${script_path}/../../.."
MERGEDREPOS="${TOP}/merged_repos.txt"
MANIFEST="${TOP}/.repo/manifests/default.xml"
BRANCH="${calyxos_branch}"
export STAGINGBRANCH="staging/${BRANCH}_${OPERATION}-${NEWTAG}"

# Source build environment (needed for aospremote)
source "${TOP}/build/envsetup.sh"

# Build list of LineageOS forked repos
PROJECTPATHS=$(grep "name=\"LineageOS/" "${MANIFEST}" | sed -n 's/.*path="\([^"]\+\)".*/\1/p')

echo "#### Old tag = ${OLDTAG} Branch = ${BRANCH} Staging branch = ${STAGINGBRANCH} ####"

# Make sure manifest and forked repos are in a consistent state
echo "#### Verifying there are no uncommitted changes on LineageOS forked AOSP projects ####"
for PROJECTPATH in ${PROJECTPATHS} .repo/manifests; do
    cd "${TOP}/${PROJECTPATH}"
    aospremote | grep -v "Remote 'aosp' created"
    if [[ -n "$(git status --porcelain)" ]]; then
        echo "Path ${PROJECTPATH} has uncommitted changes. Please fix."
        exit 1
    fi
done
echo "#### Verification complete - no uncommitted changes found ####"

# Remove any existing list of merged repos file
rm -f "${MERGEDREPOS}"

# Ditch any existing staging branches (across all projects)
repo abandon "${STAGINGBRANCH}"

# Iterate over each forked project
for PROJECTPATH in ${PROJECTPATHS}; do
    "${script_path}"/_merge_helper.sh "${PROJECTPATH}" "${@}" | tee -a "${MERGEDREPOS}"
done

unset STAGINGBRANCH

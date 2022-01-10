#!/bin/bash
#
# SPDX-FileCopyrightText: 2017, 2020-2022 The LineageOS Project
# SPDX-FileCopyrightText: 2021-2022 The Calyx Institute
#
# SPDX-License-Identifier: Apache-2.0
#

usage() {
    echo "Usage ${0} <merge|rebase> <aosp-tag> <different-ancestor-aosp-tag>"
    echo "Example ${0} merge android-12.0.0_r26 android-12.0.0_r18"
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

# Check to make sure this is being run from the top level repo dir
if [ ! -e "build/envsetup.sh" ]; then
    echo "Must be run from the top level repo dir"
    exit 1
fi

### CONSTANTS ###
readonly script_path="$(cd "$(dirname "$0")";pwd -P)"
readonly vars_path="${script_path}/../vars"

source "${vars_path}/common"

TOP="${ANDROID_BUILD_TOP}"
MERGEDREPOS="${TOP}/merged_repos_aosp.txt"
MANIFEST="${TOP}/.repo/manifests/default.xml"
export STAGINGBRANCH="staging/${OLDTAG}_${OPERATION}-${NEWTAG}"

# Build list of AOSP repos
PROJECTPATHS=$(grep -v "remote=\"gitlab" "${MANIFEST}" | grep -v "clone-depth=\"1" | sed -n 's/.*path="\([^"]\+\)".*/\1/p')

echo "#### Old tag = ${OLDTAG} New tag = ${NEWTAG} Staging branch = ${STAGINGBRANCH} ####"

# Make sure manifest and forked repos are in a consistent state
echo "#### Verifying there are no uncommitted changes on AOSP projects ####"
for PROJECTPATH in ${PROJECTPATHS} .repo/manifests; do
    cd "${TOP}/${PROJECTPATH}"
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

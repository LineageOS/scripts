#!/bin/bash
#
# SPDX-FileCopyrightText: 2017, 2020-2022 The LineageOS Project
# SPDX-FileCopyrightText: 2021-2023 The Calyx Institute
#
# SPDX-License-Identifier: Apache-2.0
#

usage() {
    echo "Usage ${0} -o <merge|rebase> -c <old-aosp-tag> -n <new-aosp-tag> -b <branch-suffix>"
}

# Verify argument count
if [ "${#}" -eq 0 ]; then
    usage
    exit 1
fi

while [ "${#}" -gt 0 ]; do
    case "${1}" in
        -o | --operation )
                OPERATION="${2}"; shift
                ;;
        -c | --old-tag )
                OLDTAG="${2}"; shift
                ;;
        -n | --new-tag )
                NEWTAG="${2}"; shift
                ;;
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

if [ -z "${OPERATION}" ]; then
    OPERATION="merge"
elif [ "${OPERATION}" != "merge" -a "${OPERATION}" != "rebase" ]; then
    usage
    exit 1
fi

### CONSTANTS ###
readonly script_path="$(cd "$(dirname "$0")";pwd -P)"
readonly vars_path="${script_path}/../../../vendor/lineage/vars"

source "${vars_path}/common"

TOP="${script_path}/../../.."
MANIFEST="${TOP}/.repo/manifests/default.xml"
BRANCH="${os_branch}"
STAGINGBRANCH="staging/${BRANCHSUFFIX}"

# Build list of forked repos
PROJECTPATHS=$(grep "name=\"LineageOS/" "${MANIFEST}" | sed -n 's/.*path="\([^"]\+\)".*/\1/p')

echo -e "\n#### Old tag = ${OLDTAG} Branch = ${BRANCH} Staging branch = ${STAGINGBRANCH} ####"

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

# Iterate over each forked project
parallel -j8 --line-buffer --tag "${script_path}"/_merge_helper.sh --project-path {} --operation "$OPERATION" --old-tag "$OLDTAG" --new-tag "$NEWTAG" --branch-suffix "$BRANCHSUFFIX" ::: "${PROJECTPATHS}"

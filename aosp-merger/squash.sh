#!/bin/bash
#
# SPDX-FileCopyrightText: 2017, 2020-2022 The LineageOS Project
# SPDX-FileCopyrightText: 2021-2023 The Calyx Institute
#
# SPDX-License-Identifier: Apache-2.0
#

usage() {
    echo "Usage ${0} -p <projectpath> -n <new-tag> -b <branch-suffix> --pixel"
}

# Verify argument count
if [ "${#}" -eq 0 ]; then
    usage
    exit 1
fi

CUSTOMPROJECTPATH=
PIXEL=false

while [ "${#}" -gt 0 ]; do
    case "${1}" in
        -p | --project-path )
                CUSTOMPROJECTPATH="${2}"; shift
                ;;
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
SQUASHBRANCH="squash/${BRANCHSUFFIX}"
BRANCH=$(git config --get branch.${STAGINGBRANCH}.merge | sed 's|refs/heads/||')
if [ -z "${BRANCH}" ]; then
    BRANCH="${os_branch}"
fi

# List of merged repos
if [[ -n "${CUSTOMPROJECTPATH}" ]]; then
    PROJECTPATHS="${CUSTOMPROJECTPATH}"
else
    PROJECTPATHS=$(cat ${MERGEDREPOS} | grep -w merge | awk '{printf "%s\n", $2}')
fi

echo -e "\n#### Branch = ${BRANCH} Squash branch = ${SQUASHBRANCH} ####"

# Make sure manifest and forked repos are in a consistent state
for PROJECTPATH in ${PROJECTPATHS} .repo/manifests; do
    cd "${TOP}/${PROJECTPATH}"
    if [[ -n "$(git status --porcelain)" ]]; then
        echo "Path ${PROJECTPATH} has uncommitted changes. Please fix."
        exit 1
    fi
done

# Iterate over each forked project
for PROJECTPATH in ${PROJECTPATHS}; do
    cd "${TOP}/${PROJECTPATH}"
    echo -e "\n#### Squashing ${PROJECTPATH} ####"
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

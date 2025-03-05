#!/bin/bash
#
# SPDX-FileCopyrightText: 2017, 2020-2022 The LineageOS Project
# SPDX-FileCopyrightText: 2021-2023 The Calyx Institute
#
# SPDX-License-Identifier: Apache-2.0
#

usage() {
    echo "Usage ${0} -n <new-tag> -b <branch-suffix>"
}

# Verify argument count
if [ "${#}" -eq 0 ]; then
    usage
    exit 1
fi

while [ "${#}" -gt 0 ]; do
    case "${1}" in
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

### CONSTANTS ###
readonly script_path="$(cd "$(dirname "$0")";pwd -P)"
readonly vars_path="${script_path}/../../../vendor/lineage/vars"

source "${vars_path}/common"

TOP="${script_path}/../../.."
SQUASHBRANCH="squash/${BRANCHSUFFIX}"
if [ ! -z "${NEWTAG}" ]; then
    TOPIC="${NEWTAG}"
else
    TOPIC="${topic}"
fi

# List of merged repos
PROJECTPATHS=$(cat ${MERGEDREPOS} | grep -w merge | awk '{printf "%s\n", $2}')

echo -e "\n#### Squash branch = ${SQUASHBRANCH} ####"

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
    echo -e "\n#### Pushing ${PROJECTPATH} squash to review ####"
    git checkout "${SQUASHBRANCH}"
    repo upload -c -y --no-verify -o topic="${TOPIC}" .
done

#!/bin/bash
#
# SPDX-FileCopyrightText: 2017, 2020-2022 The LineageOS Project
# SPDX-FileCopyrightText: 2021-2022 The Calyx Institute
#
# SPDX-License-Identifier: Apache-2.0
#

usage() {
    echo "Usage ${0} <projectpath> <merge|rebase> <oldaosptag> <newaosptag>"
}

# Verify argument count
if [ "$#" -ne 4 ]; then
    usage
    exit 1
fi

PROJECTPATH="${1}"
OPERATION="${2}"
OLDTAG="${3}"
NEWTAG="${4}"

if [ "${OPERATION}" != "merge" -a "${OPERATION}" != "rebase" ]; then
    usage
    exit 1
fi

### CONSTANTS ###
readonly script_path="$(cd "$(dirname "$0")";pwd -P)"
readonly vars_path="${script_path}/../vars"

source "${vars_path}/common"

TOP="${script_path}/../../.."
BRANCH="${calyxos_branch}"
STAGINGBRANCH="staging/${BRANCH}_${OPERATION}-${NEWTAG}"

cd "${TOP}/${PROJECTPATH}"
repo start "${STAGINGBRANCH}" .
git fetch -q --tags aosp "${NEWTAG}"

PROJECTOPERATION="${OPERATION}"

# Check if we've actually changed anything before attempting to merge
# If we haven't, just "git reset --hard" to the tag
if [[ -z "$(git diff HEAD ${OLDTAG})" ]]; then
    git reset --hard "${NEWTAG}"
    echo -e "reset\t\t${PROJECTPATH}"
    continue
fi

# Was there any change upstream? Skip if not.
if [[ -z "$(git diff ${OLDTAG} ${NEWTAG})" ]]; then
    echo -e "nochange\t\t${PROJECTPATH}"
    exit 0
fi

# Determine whether OLDTAG is an ancestor of NEWTAG
# ie is history consistent.
git merge-base --is-ancestor "${OLDTAG}" "${NEWTAG}"
# If no, print a warning message.
if [[ "$?" -eq 1 ]]; then
    echo -n "#### Warning: project ${PROJECTPATH} old tag ${OLDTAG} is not an ancestor "
    echo    "of new tag ${NEWTAG} ####"
fi

if [[ "${PROJECTOPERATION}" == "merge" ]]; then
    echo "#### Merging ${NEWTAG} into ${PROJECTPATH} ####"
    git merge --no-edit --log "${NEWTAG}"
elif [[ "${PROJECTOPERATION}" == "rebase" ]]; then
    echo "#### Rebasing ${PROJECTPATH} onto ${NEWTAG} ####"
    git rebase --onto "${NEWTAG}" "${OLDTAG}"
fi

CONFLICT=""
if [[ -n "$(git status --porcelain)" ]]; then
    CONFLICT="conflict-"
fi
echo -e "${CONFLICT}${PROJECTOPERATION}\t\t${PROJECTPATH}"

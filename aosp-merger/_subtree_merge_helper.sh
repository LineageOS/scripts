#!/bin/bash
#
# SPDX-FileCopyrightText: 2017, 2020-2022 The LineageOS Project
# SPDX-FileCopyrightText: 2021-2022 The Calyx Institute
#
# SPDX-License-Identifier: Apache-2.0
#

usage() {
    echo "Usage ${0} <projectpath> <oldaosptag> <newaosptag>"
}

# Verify argument count
if [ "$#" -ne 3 ]; then
    usage
    exit 1
fi

PROJECTPATH="${1}"
OLDTAG="${2}"
NEWTAG="${3}"

### CONSTANTS ###
readonly script_path="$(cd "$(dirname "$0")";pwd -P)"
readonly vars_path="${script_path}/../../../vendor/lineage/vars"

source "${vars_path}/common"

readonly hook="${script_path}/prepare-commit-msg"

TOP="${script_path}/../../.."
BRANCH="${lineageos_branch}"

cd "${TOP}/${PROJECTPATH}"
# Ditch any existing staging branches
repo abandon "${STAGINGBRANCH}" .
repo start "${STAGINGBRANCH}" .
git fetch -q --force --tags "$(cat .gitupstream)" "${NEWTAG}"

[[ ! -e .git/hooks/prepare-commit-msg ]] && cp "${hook}" .git/hooks/
chmod +x .git/hooks/prepare-commit-msg

# Was there any change upstream? Skip if not.
if [[ -z "$(git diff ${OLDTAG} ${NEWTAG})" ]]; then
    echo -e "nochange\t\t${PROJECTPATH}" | tee -a "${MERGEDREPOS}"
    repo abandon "${STAGINGBRANCH}" .
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

CONFLICT=""

echo "#### Merging ${NEWTAG} into ${PROJECTPATH} ####"
git merge --no-commit --log "${NEWTAG}" && git commit --no-edit
if [[ -n "$(git status --porcelain)" ]]; then
    CONFLICT="conflict-"
fi
read -p "Waiting for conflict resolution before continuing. Press enter when done."

find -mindepth 2 -type f -name .gitupstream | cut -d / -f 2- | sed s#/.gitupstream## | while read -r subtree; do
    gitupstream="${subtree}/.gitupstream"
    git fetch -q --force --tags "$(cat ${gitupstream})" "${NEWTAG}"
    git merge -X subtree="$subtree" --no-commit --log "${NEWTAG}" && git commit --no-edit
    if [[ -n "$(git status --porcelain)" && -z "${CONFLICT}" ]]; then
        CONFLICT="conflict-"
    fi
    read -p "Waiting for conflict resolution before continuing. Press enter when done."
done

# Check if we've actually changed anything after the merge
# If we haven't, just abandon the branch
if [[ -z "$(git diff HEAD m/${lineageos_branch})" && -z "$(git status --porcelain)" ]]; then
    echo -e "nochange\t\t${PROJECTPATH}" | tee -a "${MERGEDREPOS}"
    repo abandon "${STAGINGBRANCH}" .
    exit 0
fi

echo -e "${CONFLICT}merge\t\t${PROJECTPATH}" | tee -a "${MERGEDREPOS}"

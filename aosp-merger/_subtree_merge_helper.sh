#!/bin/bash
#
# SPDX-FileCopyrightText: 2017, 2020-2022 The LineageOS Project
# SPDX-FileCopyrightText: 2021-2022 The Calyx Institute
#
# SPDX-License-Identifier: Apache-2.0
#

usage() {
    echo "Usage ${0} -p <projectpath> -o <merge|rebase> -c <old-tag> -n <new-tag> -b <branch-suffix>"
}

# Verify argument count
if [ "${#}" -eq 0 ]; then
    usage
    exit 1
fi

while [ "${#}" -gt 0 ]; do
    case "${1}" in
        -p | --project-path )
                PROJECTPATH="${2}"; shift
                ;;
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

readonly hook="${script_path}/prepare-commit-msg"

TOP="${script_path}/../../.."
BRANCH="${os_branch}"
STAGINGBRANCH="staging/${BRANCHSUFFIX}"

cd "${TOP}/${PROJECTPATH}"
# Ditch any existing staging branches
repo abandon "${STAGINGBRANCH}" .
repo start "${STAGINGBRANCH}" .
if [ -f ".gitupstream" ]; then
    git fetch -q --force --tags "$(cat .gitupstream)" "${NEWTAG}"
else
    git fetch -q --force --tags aosp "${NEWTAG}"
fi

[[ ! -e .git/hooks/prepare-commit-msg ]] && cp "${hook}" .git/hooks/
chmod +x .git/hooks/prepare-commit-msg

if [ ! -z "${OLDTAG}" ]; then
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
fi

CONFLICT=""

echo "#### Merging ${NEWTAG} into ${PROJECTPATH} ####"
git merge --no-commit --log "${NEWTAG}"

if [[ -z "$(git diff HEAD)" ]]; then
    echo "#### Skipping empty merge ####"
    git reset --hard
else
    git commit --no-edit
    if [[ -n "$(git status --porcelain)" ]]; then
        CONFLICT="conflict-"
    fi
    read -p "Waiting for conflict resolution before continuing. Press enter when done."

    echo $(git log  -1 --pretty=%b | tail -2) > .git/CHANGE_ID
fi

for subtree in `find -mindepth 2 -type f -name .gitupstream | cut -d / -f 2- | sed s#/.gitupstream##`; do
    gitupstream="${subtree}/.gitupstream"
    git fetch -q --force --tags "$(cat ${gitupstream})" "${NEWTAG}"
    git merge -X subtree="$subtree" --no-commit --log "${NEWTAG}"

    if [[ -z "$(git diff HEAD)" ]]; then
        echo "#### Skipping empty merge on ${subtree} ####"
        git reset --hard
        continue
    fi

    git commit --no-edit
    if [[ -n "$(git status --porcelain)" && -z "${CONFLICT}" ]]; then
        CONFLICT="conflict-"
    fi
    read -p "Waiting for conflict resolution before continuing. Press enter when done."

    if [[ ! -f ".git/CHANGE_ID" ]]; then
        echo $(git log  -1 --pretty=%b | tail -2) > .git/CHANGE_ID
    fi
done

# Check if we've actually changed anything after the merge
# If we haven't, just abandon the branch
if [[ -z "$(git diff HEAD m/${os_branch})" && -z "$(git status --porcelain)" ]]; then
    echo -e "nochange\t\t${PROJECTPATH}" | tee -a "${MERGEDREPOS}"
    repo abandon "${STAGINGBRANCH}" .
    exit 0
fi

echo -e "${CONFLICT}${OPERATION}\t\t${PROJECTPATH}" | tee -a "${MERGEDREPOS}"

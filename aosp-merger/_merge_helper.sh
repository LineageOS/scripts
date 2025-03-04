#!/bin/bash
#
# SPDX-FileCopyrightText: 2017, 2020-2022 The LineageOS Project
# SPDX-FileCopyrightText: 2021-2023 The Calyx Institute
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

# Source build environment (needed for aospremote)
source "${TOP}/build/envsetup.sh"

BRANCH="${os_branch}"
STAGINGBRANCH="staging/${BRANCHSUFFIX}"

cd "${TOP}/${PROJECTPATH}"

PREVIOUSBRANCH="$(git branch --show-current 2>/dev/null)"

# Ditch any existing staging branches
if git show-ref --verify --quiet refs/heads/"${STAGINGBRANCH}"; then
    repo abandon "${STAGINGBRANCH}" .
fi
repo start --head "${STAGINGBRANCH}" .
if [ -f ".gitupstream" ]; then
    git fetch -q --force --tags "$(cat .gitupstream)" "${NEWTAG}"
else
    aospremote | grep -v "Remote 'aosp' created"
    git fetch -q --force --tags aosp "${NEWTAG}"
fi

[[ ! -e .git/hooks/prepare-commit-msg ]] && cp "${hook}" .git/hooks/
chmod +x .git/hooks/prepare-commit-msg

if [ ! -z "${OLDTAG}" ]; then
    # Was there any change upstream? Skip if not.
    if [[ -z "$(git diff --no-ext-diff ${OLDTAG} ${NEWTAG})" ]]; then
        echo -e "nochange\t\t${PROJECTPATH}" | tee -a "${MERGEDREPOS}"
        repo abandon "${STAGINGBRANCH}" .
        if [ -n "$PREVIOUSBRANCH" ]; then
            git checkout "$PREVIOUSBRANCH"
        fi
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

if [[ "${OPERATION}" == "merge" ]]; then
    echo -e "\n#### Merging ${NEWTAG} into ${PROJECTPATH} ####"
    git merge --no-commit --log "${NEWTAG}" && git commit --no-edit

    # Check if we've actually changed anything after the merge
    # If we haven't, just abandon the branch
    if [[ -z "$(git diff --no-ext-diff HEAD m/${os_branch})" && -z "$(git status --porcelain)" ]]; then
        echo -e "nochange\t\t${PROJECTPATH}" | tee -a "${MERGEDREPOS}"
        repo abandon "${STAGINGBRANCH}" .
        if [ -n "$PREVIOUSBRANCH" ]; then
            git checkout "$PREVIOUSBRANCH"
        fi
        exit 0
    fi
elif [[ "${OPERATION}" == "rebase" ]]; then
    echo -e "\n#### Rebasing ${PROJECTPATH} onto ${NEWTAG} ####"
    git rebase --onto "${NEWTAG}" "${OLDTAG}"
fi

CONFLICT=""
if [[ -n "$(git status --porcelain)" ]]; then
    CONFLICT="conflict-"
fi
echo -e "${CONFLICT}${OPERATION}\t\t${PROJECTPATH}" | tee -a "${MERGEDREPOS}"

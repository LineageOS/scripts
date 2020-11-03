#!/bin/bash
#
# Copyright (C) 2017 The LineageOS Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
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

# Check to make sure this is being run from the top level repo dir
if [ ! -e "build/envsetup.sh" ]; then
    echo "Must be run from the top level repo dir"
    exit 1
fi

# Source build environment (needed for aospremote)
. build/envsetup.sh

TOP="${ANDROID_BUILD_TOP}"
MERGEDREPOS="${TOP}/merged_repos.txt"
MANIFEST="${TOP}/.repo/manifests/default.xml"
BRANCH=$(git -C ${TOP}/.repo/manifests.git config --get branch.default.merge | sed 's#refs/heads/##g')
STAGINGBRANCH="staging/${BRANCH}_${OPERATION}-${NEWTAG}"

# Build list of LineageOS forked repos
PROJECTPATHS=$(grep "name=\"LineageOS/" "${MANIFEST}" | sed -n 's/.*path="\([^"]\+\)".*/\1/p')

echo "#### Old tag = ${OLDTAG} Branch = ${BRANCH} Staging branch = ${STAGINGBRANCH} ####"

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

# Remove any existing list of merged repos file
rm -f "${MERGEDREPOS}"

# Sync and detach from current branches
repo sync -d

# Ditch any existing staging branches (across all projects)
repo abandon "${STAGINGBRANCH}"

# Iterate over each forked project
for PROJECTPATH in ${PROJECTPATHS}; do
    cd "${TOP}/${PROJECTPATH}"
    repo start "${STAGINGBRANCH}" .
    aospremote | grep -v "Remote 'aosp' created"
    git fetch -q --tags aosp "${NEWTAG}"

    PROJECTOPERATION="${OPERATION}"

    # Check if we've actually changed anything before attempting to merge
    # If we haven't, just "git reset --hard" to the tag
    if [[ -z "$(git diff HEAD ${OLDTAG})" ]]; then
        git reset --hard "${NEWTAG}"
        echo -e "reset\t\t${PROJECTPATH}" | tee -a "${MERGEDREPOS}"
        continue
    fi

    # Was there any change upstream? Skip if not.
    if [[ -z "$(git diff ${OLDTAG} ${NEWTAG})" ]]; then
        echo -e "nochange\t\t${PROJECTPATH}" | tee -a "${MERGEDREPOS}"
        continue
    fi

    # Determine whether OLDTAG is an ancestor of NEWTAG
    # ie is history consistent.
    git merge-base --is-ancestor "${OLDTAG}" "${NEWTAG}"
    # If no, force rebase.
    if [[ "$?" -eq 1 ]]; then
        echo -n "#### Project ${PROJECTPATH} old tag ${OLD} is not an ancestor "
        echo    "of new tag ${NEWTAG}, forcing rebase ####"
        PROJECTOPERATION="rebase"
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
    echo -e "${CONFLICT}${PROJECTOPERATION}\t\t${PROJECTPATH}" | tee -a "${MERGEDREPOS}"
done

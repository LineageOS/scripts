#!/bin/bash
#
# SPDX-FileCopyrightText: 2017 The LineageOS Project
#
# SPDX-License-Identifier: Apache-2.0
#

#####
# Rebase your local working branches onto a new "upstream" branch.
# Local branch list is defined in branches.list
# (and can be created with branches_save.sh)
# If the upstream branch doesn't exist (eg perhaps in lineage-sdk),
# simply switch the working branch instead.

if [ ! -e "build/envsetup.sh" ]; then
    echo "Must run from root of repo"
    exit 1
fi

if [ "$#" -ne 1 ]; then
    echo "Usage ${0} <branch to rebase on top of>"
    exit 1
fi
REBASEONTO="${1}"

TOP="${PWD}"
BRANCHLIST="${TOP}/branches.list"

cat "${BRANCHLIST}" | while read l; do
    set ${l}
    PROJECTPATH="${1}"
    BRANCH="${2}"
    NEWBRANCH="${2}-rebase"
    cd "${TOP}/${PROJECTPATH}"

    # Sanity check
    if [[ -n "$(git status --porcelain)" ]]; then
        echo -n "!!!! Project ${PROJECTPATH} has uncommitted files, "
        echo    "not switching to branch ${BRANCH} (skipping) !!!!"
        continue
    fi

    # Check the $REBASEONTO branch actually exists
    git show-ref "refs/heads/${REBASEONTO}" >/dev/null
    if [ "$?" -ne 0 ]; then
        # Nope
        echo -n "#### Project ${PROJECTPATH} branch ${REBASEONTO} does not exist, "
        echo    "switching to ${BRANCH} instead ####"
        git checkout "${BRANCH}"
    else
        echo "#### Creating ${PROJECTPATH} branch ${NEWBRANCH} from ${BRANCH} ####"
        repo abandon "${NEWBRANCH}" .
        repo start "${NEWBRANCH}" .
        git reset --hard "${BRANCH}"
        echo -n "#### Project ${PROJECTPATH} Rebasing branch ${NEWBRANCH} "
        echo    "on top of ${REBASEONTO} ####"
        git rebase --onto "${REBASEONTO}"
    fi
done

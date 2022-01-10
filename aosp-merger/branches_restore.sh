#!/bin/bash
#
# SPDX-FileCopyrightText: 2017 The LineageOS Project
#
# SPDX-License-Identifier: Apache-2.0
#

if [ ! -e "build/envsetup.sh" ]; then
    echo "Must run from root of repo"
    exit 1
fi

TOP="${PWD}"
BRANCHLIST="${TOP}/branches.list"

cat "${BRANCHLIST}" | while read l; do
    set ${l}
    PROJECTPATH="${1}"
    BRANCH="${2}"
    cd "${TOP}/${PROJECTPATH}"

    # Check if we're on this branch already
    CURBRANCH=$(git status -b --porcelain | head -1 | awk '{print $2}' | sed 's/\.\.\..*//')
    if [ "${CURBRANCH}" == "${BRANCH}" ]; then
        echo "#### Project ${PROJECTPATH} is already on branch ${BRANCH} ####"
        continue
    fi

    # Sanity check
    if [[ -n "$(git status --porcelain)" ]]; then
        echo -n "#!#! Project ${PROJECTPATH} has uncommitted files, "
        echo    "not switching to branch ${BRANCH} #!#!"
        exit 1
    fi

    echo "#### Project ${PROJECTPATH} Switching to branch ${BRANCH} ####"
    git checkout "${BRANCH}"
done

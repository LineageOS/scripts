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

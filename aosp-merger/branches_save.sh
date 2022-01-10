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

# Example repo status output:
#project build/make/                             branch x
#project device/huawei/angler/                   branch x

repo status | grep '^project ' | while read l; do
    set ${l}
    PROJECTPATH=$(echo ${2} | sed 's|/$||')
    BRANCH="${4}"
    echo "${PROJECTPATH} ${BRANCH}"
done | sort > "${BRANCHLIST}"

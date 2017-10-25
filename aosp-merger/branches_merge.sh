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

if [ "$#" -ne 1 ]; then
    echo "Usage $0 <branch to merge>"
    exit 1
fi
TOMERGE="$1"

TOP="$PWD"
BRANCHLIST="$TOP/branches.list"

cat "$BRANCHLIST" | while read l; do
    set $l
    PROJECTPATH="$1"
    BRANCH="$2"
    cd "$TOP/$PROJECTPATH"

    # Sanity check
    git status | grep "nothing to commit, working directory clean" >/dev/null
    if [ ${PIPESTATUS[1]} -ne 0 ]; then
        echo "#!#! Project $PROJECTPATH has uncommitted files, not switching to branch $BRANCH #!#!"
        exit 1
    fi

    echo "#### Project $PROJECTPATH Switching to branch $BRANCH ####"
    git checkout "$BRANCH"
    echo "#### Project $PROJECTPATH Merging branch $TOMERGE ####"
    git merge "$TOMERGE"
done

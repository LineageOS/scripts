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
    echo "Usage $0 <branch to rebase on top of>"
    exit 1
fi
REBASEONTO="$1"

TOP="$PWD"
BRANCHLIST="$TOP/branches.list"

cat "$BRANCHLIST" | while read l; do
    set $l
    PROJECTPATH="$1"
    BRANCH="$2"
    NEWBRANCH="${2}-rebase"
    cd "$TOP/$PROJECTPATH"

    # Sanity check
    git status | grep "nothing to commit, working directory clean" >/dev/null
    if [ ${PIPESTATUS[1]} -ne 0 ]; then
        echo "!!!! Project $PROJECTPATH has uncommitted files, not switching to branch $BRANCH (skipping) !!!!"
        continue
    fi

    # Check the $REBASEONTO branch actually exists
    git show-ref "refs/heads/$REBASEONTO" >/dev/null
    if [ "$?" -ne 0 ]; then
        # Nope
        echo "#### Project $PROJECTPATH branch $REBASEONTO does not exist, switching to $BRANCH instead ####"
        git checkout "$BRANCH"
    else
        echo "#### Creating $PROJECTPATH branch $NEWBRANCH from $BRANCH ####"
        repo abandon "$NEWBRANCH" .
        repo start "$NEWBRANCH" .
        git reset --hard "$BRANCH"
        echo "#### Project $PROJECTPATH Rebasing branch $NEWBRANCH on top of $REBASEONTO ####"
        git rebase --onto "$REBASEONTO"
    fi
done

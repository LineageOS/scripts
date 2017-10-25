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

TOP="$PWD"
BRANCHLIST="$TOP/branches.list"

# Example repo status output:
#project build/make/                             branch x
#project device/huawei/angler/                   branch x

repo status | grep '^project ' | while read l; do
    set $l
    PROJECTPATH="$2"
    BRANCH="$4"
    echo "$PROJECTPATH $BRANCH"
done | sort > "$BRANCHLIST"

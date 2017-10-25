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

TMPDIR=$(mktemp -d)

# Check to make sure this is being run from the root lineage dir
if [ ! -d ".repo" ]; then
  echo "This script must be run from the root lineage dir"
  exit
else
  LINEAGE_ROOT=$(pwd)
fi

. build/envsetup.sh
repo forall -c 'git reset --hard HEAD; git clean -fd'
repo abandon merge
repo sync -d
rm $LINEAGE_ROOT/merged_repos.txt

# Fetch our changed repos from the manifest
changed_repos=$(grep "LineageOS" .repo/manifest.xml)
echo $changed_repos | grep -o -P "path=\".*?\"" > $TMPDIR/repos.txt

sed -i 's/path=\"//g' $TMPDIR/repos.txt
sed -i 's/\"//g' $TMPDIR/repos.txt

while read line; do
  cd $line
  repo start merge .
  aospremote
  git fetch --tags aosp $1
  git merge $1
  if [[ -n "$(git status --short)" ]]; then
    echo -e "conflict\t$line" >> $LINEAGE_ROOT/merged_repos.txt
    echo -e "conflict\t$line"
  else
    echo -e "merged\t\t$line" >> $LINEAGE_ROOT/merged_repos.txt
    echo -e "merged\t\t$line"
  fi
  cd $LINEAGE_ROOT
done < $TMPDIR/repos.txt

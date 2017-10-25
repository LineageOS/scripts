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

OPERATION=$1
NEWTAG=$2
OLDTAG=$(grep "tags\/android" .repo/manifest.xml | sed 's/^ *//g;s/revision=\"refs\/tags\///g;s/\" \/>//g')
BRANCH=$(grep "default revision" .repo/manifest.xml | sed 's/^ *//g;s/<default revision=\"refs\/heads\///g;s/\"//g')

# Check to make sure this is being run from the root lineage dir
if [ ! -d ".repo" ]; then
  echo "This script must be run from the root lineage dir"
  exit
else
  LINEAGE_ROOT=$(pwd)
fi

# Make sure there aren't any rogue changes in the manifest
cd .repo/manifests
git checkout
cd ../..

. build/envsetup.sh
repo forall -c 'git reset --hard HEAD; git clean -fd'
repo abandon staging/${BRANCH}_${OPERATION}-${NEWTAG}
repo sync -d
rm $LINEAGE_ROOT/merged_repos.txt

# Fetch our changed repos from the manifest
changed_repos=$(grep "LineageOS" .repo/manifest.xml)
echo $changed_repos | grep -o -P "path=\".*?\"" > $TMPDIR/repos.txt

sed -i 's/path=\"//g;s/\"//g' $TMPDIR/repos.txt

while read line; do
  cd $line
  repo start staging/${BRANCH}_${OPERATION}-${NEWTAG} .
  aospremote
  git fetch --tags aosp $NEWTAG
  # Check if we've actually changed anything before attempting to merge
  # If we haven't, just "git reset --hard" to the tag
  if [[ -n "$(git diff HEAD $OLDTAG)" ]]; then
    if [[ $OPERATION == "merge" ]]; then
      git merge $NEWTAG
    elif [[ $OPERATION == "rebase" ]]; then
      git rebase $NEWTAG
    else
      echo "invalid operation"
      exit
    fi
    if [[ -n "$(git status --short)" ]]; then
      echo -e "conflict\t$line" >> $LINEAGE_ROOT/merged_repos.txt
      echo -e "conflict\t$line"
    else
      if [[ $OPERATION == "merge" ]]; then
       echo -e "merged\t\t$line" >> $LINEAGE_ROOT/merged_repos.txt
       echo -e "merged\t\t$line"
     elif [[ $OPERATION == "rebase" ]]; then
       echo -e "rebased\t\t$line" >> $LINEAGE_ROOT/merged_repos.txt
       echo -e "rebased\t\t$line"
     fi
    fi
  else
    git reset --hard $NEWTAG
    echo -e "reset\t\t$line" >> $LINEAGE_ROOT/merged_repos.txt
    echo -e "reset\t\t$line"
  fi
  cd $LINEAGE_ROOT
done < $TMPDIR/repos.txt

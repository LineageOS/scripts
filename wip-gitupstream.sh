#!/bin/bash
#
# Work in progress git upstream file, will be moved
# Put here to make discussion / feedback easier by having pseudocode
#
# Per-repo files:
# .gitupstream-aosp # or caf / clo / etc
# url revision # Or variables (e.g. $common_aosp_tag)
#
# Uses:
# 1. upstream merge
# git pull $(cat .gitupstream-aosp) # or caf / clo / etc. Can set variable first if used (e.g. $common_aosp_tag)
# 2. aospremote for trickier projects # or cafremote
# git remote add aosp $(cat .gitupstream-aosp | cut -d ' ' -f 1)
# 3. ?

# CAF / CLO

# Option 1, per group
for repo in $(repo list -g sdm660); do
	export group_rev=sometag # Get tag from vars mapping
	git -C $repo pull --no-edit $(cat $repo/.gitupstream-clo) # TODO Call merger script instead
done

# Option 2, all at once
for repo in $(repo list -g qcom); do # Or find . -type f -name .gitupstream-clo
	group=from manifest # Somehow get group from manifest
	export group_rev=sometag # Get tag from vars mapping
	git -C $repo pull --no-edit $(cat $repo/.gitupstream-clo) # TODO Call merger script instead

# AOSP (not strictly needed for all repos, or even for merging given we have the script)
for repo in $(find . -type -f -name .gitupstream-aosp | get path); do
	export common_aosp_tag # Set in vars/common
	git -C $repo pull --no-edit $(cat $repo/.gitupstream-aosp) # TODO Call a merger script
done

#!/bin/bash
#
# Work in progress git upstream file, will be moved
# Put here to make discussion / feedback easier by having pseudocode
#
# Per-repo files:
# .gitupstream
# url
#
# Uses:
# 1. upstream merge
# git pull $(cat .gitupstream) $group_rev # or caf / clo / etc. Can set variable first if used (e.g. $common_aosp_tag)
# 2. aospremote for trickier projects # or cafremote
# git remote add aosp $(cat .gitupstream-aosp | cut -d ' ' -f 1)
# 3. ?

# use bash strict mode
set -euo pipefail

# TODO: Move to vars
declare -A group_revision
group_revision[qssi]=LA.QSSI.12.0.r1-07800-qssi.0
group_revision[msm8953_64]=LA.UM.10.6.2.r1-01900-89xx.0
group_revision[sdm660_64]=LA.UM.10.2.1.r1-03800-sdm660.0
group_revision[sdm845]=LA.UM.10.3.r1-01700-sdm845.0
group_revision[msmnile]=LA.UM.9.1.r1-11900.02-SMxxx0.QSSI12.0
group_revision[kona]=LA.UM.9.12.r1-14300-SMxx50.0
group_revision[lahaina]=LA.UM.9.14.r1-19600.01-LAHAINA.QSSI12.0

group=$1

for repo in $(repo list -g $group); do
	export revision=${group_revision[$group]} # Get tag from vars mapping
	# TODO Call merger script instead
	git -C $repo pull --no-commit --log $(cat $repo/.gitupstream) ${group_rev} && git commit --no-edit
done

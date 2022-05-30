#!/bin/bash
#
# SPDX-FileCopyrightText: 2022 The LineageOS Project
#
# SPDX-License-Identifier: Apache-2.0
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

usage() {
    echo "Usage ${0} <group>"
}

# Verify argument count
if [ "$#" -ne 1 ]; then
    usage
    exit 1
fi

GROUP="${1}"

### CONSTANTS ###
readonly script_path="$(cd "$(dirname "$0")";pwd -P)"
readonly vars_path="${script_path}/../../vendor/lineage/vars"

source "${vars_path}/qcom"

TOP="${script_path}/../.."

for repo in $(repo list -p -g ${GROUP}); do
    export revision=${group_revision[${GROUP}]} # Get tag from vars mapping
    # TODO Call merger script instead
    git -C "${TOP}/${repo}" pull --no-commit --log $(cat ${TOP}/${repo}/.gitupstream) ${revision} && git -C "${TOP}/${repo}" commit --no-edit
done

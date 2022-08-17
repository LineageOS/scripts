#!/bin/bash
#
# SPDX-FileCopyrightText: 2017, 2020-2022 The LineageOS Project
# SPDX-FileCopyrightText: 2021-2022 The Calyx Institute
#
# SPDX-License-Identifier: Apache-2.0
#

usage() {
    echo "Usage ${0}"
}

# Verify argument count
if [ "${#}" -gt 0 ]; then
    usage
    exit 1
fi

### CONSTANTS ###
readonly script_path="$(cd "$(dirname "$0")";pwd -P)"
readonly vars_path="${script_path}/../../../vendor/lineage/vars"

source "${vars_path}/common"

TOP="${script_path}/../../.."
MANIFEST="${TOP}/.repo/manifests/default.xml"
TAG="${common_aosp_tag}"
BRANCH="${os_branch}"

# Source build environment (needed for calyxremote)
source "${TOP}/build/envsetup.sh"

# Build list of forked repos
PROJECTPATHS=$(grep "name=\"LineageOS/" "${MANIFEST}" | sed -n 's/.*path="\([^"]\+\)".*/\1/p')

echo "#### Tag = ${TAG} Branch = ${BRANCH} ####"
read -p "Press enter to begin pushing upstream branch, tag and downstream branch."

# Iterate over each forked project
for PROJECTPATH in ${PROJECTPATHS}; do
    cd "${TOP}/${PROJECTPATH}"
    echo "#### Pushing upstream branch, tag and downstream branch for ${PROJECTPATH} ####"
    git fetch -q --force --tags aosp "${TAG}"
    TAG_SHA1=$(git rev-parse "${TAG}"^{})
    lineageremote | grep -v "Remote 'lineage' created"
    git push -o skip-validation lineage ${TAG_SHA1}:refs/heads/${BRANCH}
done

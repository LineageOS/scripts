#!/usr/bin/env bash

set -euo pipefail

TMPDIR="$(mktemp -d "${TMPDIR:-tmp}.XXXXXX")"
trap "rm -rf '${TMPDIR}'" EXIT
export TMPDIR

git clone https://github.com/GrapheneOS/android-prepare-vendor --branch=11 ${TMPDIR}/android-prepare-vendor-11 --depth=1 --single-branch
"${TMPDIR}/android-prepare-vendor-11/scripts/download-nexus-image.sh" \
  --device "$DEVICE" --buildID "$BUILD" --output "$TMPDIR" --yes
factory_image="$(find "$TMPDIR" -iname "*$DEVICE*$BUILD-factory*.tgz" -or \
  -iname "*$DEVICE*$BUILD-factory*.zip" | head -1)"
PATH="$PATH:/sbin:${TMPDIR}/android-prepare-vendor-11/hostTools/$(uname -s)/bin" \
  "${TMPDIR}/android-prepare-vendor-11/scripts/extract-factory-images.sh" \
  --input "$factory_image" --output "$TMPDIR" \
  --conf-file "${TMPDIR}/android-prepare-vendor-11/${DEVICE}/config.json" \
  --debugfs
mv "$(dirname "$(find "${TMPDIR}" -name carrier_list.pb | head -1)")" .

#!/usr/bin/env bash

set -euo pipefail

curl -fS \
  'https://android.googlesource.com/platform/packages/providers/TelephonyProvider/+/master/assets/latest_carrier_id/carrier_list.pb?format=TEXT' | \
  base64 --decode > carrier_list.pb

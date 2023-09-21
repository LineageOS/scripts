## Pixel Scripts

### Variables

`${TOP}/vendor/lineage/vars/` - This directory stores all variables for repositories that have upstreams that are regularly merged.

Standard Variables:

`$deviceName` - e.g. `sargo`, `redfin`, `coral` - Stores the following data:

* `firmware_partitions` - A matrix of the partition names of proprietary firmware images relevant to this device
* `device_repos` - A matrix of the file-paths of relevant AOSP repositories this device depends on.
* `build_id` - Previous/current device stock build ID tags
* `build_number` - Previous/current device stock build number strings
* `image_url` - Direct link to device's latest factory image
* `image_sha256` - SHA256 sum of device's latest factory image
* `flash_url` - Stores a formatted link to Google's web-based [Flash tool](https://flash.android.com/welcome) which brings up the device's latest available image, additionally is used to fetch the data used to create build fingerprint changes
* `ota_url` - Direct link to device's latest OTA image
* `ota_sha256` - SHA256 sum of device's latest OTA image
* `security_patch` - The device's stock vendor security patch level from the device's latest factory image

`$kernelName` - Stores the following data

* `{prev_,}common_aosp_tag` - Previous/current tracked AOSP kernel tag for the relevant device/platform

See `../aosp-merger/README.md` for more

### Scripts and usage

`all.sh` - Parallelly downloads factory images for all supported pixels in vars/pixels, and extracts files/firmware

`build-desc-fingerprint.sh` - Updates build description/fingerprint in all Pixel device tree forks, and commits them, pulled from relevant `$deviceName` variable files

`device.sh` - Downloads single device factory images/OTA images and extracts files/firmware for it. e.g. `device.sh raven`

`download.sh` - Downloads single device factory images - e.g. `download.sh raven`

`update-any-var.sh` - Update any var in `vendor/lineage/vars` - e.g. `update-any-var.sh build_id TQ1A.230105.001.A2 bluejay panther`

`update-device-vars.sh` - Automatically update all `$deviceName` variables of supported devices after running `download.sh`.

`extract-factory-image.sh` - Extracts factory image contents for a single device from already downloaded images. e.g. `extract-factory-image.sh raven`

`firmware.sh` - Extracts firmware for a single device from already downloaded images. e.g. `firmware.sh raven`

`get-new-device-vars.py` - For internal use by many of the scripts referenced above

Relevant cross-script variables:

`WORK_DIR` - Tell the scripts where to save factory images, defaults to `/tmp/pixel`. e.g. `export WORK_DIR=/mnt/android/stock/`

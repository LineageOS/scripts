## LineageOS Merger Scripts

### Variables

`${TOP}/vendor/lineage/vars/` - This directory stores all variables for repositories that have upstreams that are regularly merged.

Standard Variables:

`common` - Stores the following data:

* `os_branch` - Previous/current LineageOS version
* `device_branch` - Previous/current branch name
* `{prev_,}common_aosp_tag` - Previous/current tracked AOSP tag
* `common_aosp_build_id` - Previous/current build ID string
* `topic` - The name of the topic to be used when pushing merges of newer tags to [Gerrit](https://review.lineageos.org) for review before merging

Special Variables:

`$platformName` - e.g. `qcom` - These files store tags specific to relevant non-AOSP repositories where upstream repos are regularly merged, such as CAF/CLO repositories.

* e.g. `qcom` - Stores names of relevant SoC platforms mapped to the tag we currently track for that platform's repositories

`devices` - This file stores the matrix of devices we currently merge upstream repositories monthly for

`pixels` - This file stores the matrix of Pixel devices we currently merge upstream AOSP repositories monthly for, which correlates directly to the current list of Google supported Pixel devices

`kernel_repos` - This file stores a matrix of kernel-paths relevant to AOSP devices we currently merge upstream AOSP repositories monthly for

See `../pixel/README.md` for more

### Scripts and usage

See `../pixel/README.md` for scripts to update Pixels

### Workflows

To merge a new AOSP tag platform-wide:

1. Wait for AOSP tags to show in https://android.googlesource.com/platform/manifest/

2. Wait for Pixel kernel tags to show in a post in https://groups.google.com/g/android-building

3. Edit `${TOP}/.repo/manifests/default.xml` with the new main tag

4. Edit `${TOP}/.repo/manifests/snippets/lineage.xml` and replace any existing repo with non-pinned custom tag set with the new kernel tag from latest gen Pixel - e.g. `android-13.0.0_r0.55`

5. Edit `${TOP}/.repo/manifests/snippets/pixel.xml` and replace all entries with the relevant Pixel kernel tags. commit the above changes

6. Upload `LineageOS/android` change generated to [Gerrit](https://review.lineageos.org)

7. Execute `repo sync` on the working tree

8.  Edit `${TOP}/vendor/lineage/vars/common` moving the currently tracked tag from `common_aosp_tag` to `prev_common_aosp_tag`, then updating `common_aosp_tag` to reflect the newly tracked tag, and then do the same for `prev_common_aosp_build_id` and `common_aosp_build_id` - lastly, update the `topic` variable to reflect the current month

9. Run `aosp-merger/aosp-merger.sh`, this will take some time, and reads all the variables you set up above while merging the new tags to all relevant tracked repos. This will likely create conflicts on some forked repository, and will ask you to resolve them. It will then issue a final check to ask you if you'd like to upload the merge to gerrit, then after approval uploads the merge to Gerrit for review.

10. Once testing of the merge is completed, a global committer or higher can run `aosp-merger/aosp-merger.sh submit-platform` to push the merge of the new tag to the HEAD of all relevant forked repositories

11. Directly after `submit-platform` is run, a Project Director must merge the `LineageOS/android` change on Gerrit uploaded as part of step 6 above

To merge a new AOSP tag to all currently Google supported Pixel devices and their relevant dependency repositories:

1. Wait for factory images to show up in https://developers.google.com/android/images

2. To discern build ID, the relevant `$deviceName` variable:

   e.g. `pixel/update-any-var.sh build_id TQ2A.230305.008.C1 sunfish bramble redfin barbet cheetah`

3. Git commit the `vendor/lineage/vars` variable updates and upload to Gerrit

4. Run `aosp-merger/aosp-merger.sh devices` to merge newly entered AOSP tags to all supported device's device-tree and dependencies, and upload the merges to Gerrit

5. Run `aosp-merger/aosp-merger.sh kernels` to merge newly entered AOSP kernel tags to all supported device's kernel-tree and dependencies, and upload the merges to Gerrit

6. Download pixel factory images, extract files and firmware - e.g. `source ${TOP}/vendor/lineage/vars/devices && for device in devices; do pixel/device.sh $device done`

7. `cd` to each relevant device's `vendor/$oem/$deviceName` repository, as well as `vendor/firmware` and `git add`/`git commit` the updated files

   TODO: Automate this in the future

8. Update the build description/fingerprint for all supported Pixels by running `pixel/build-desc-fingerprint.sh` - after this you need to manually `cd` to each of the supported Pixel trees and upload the build description/fingerprint commits to Gerrit for review

   TODO: Automate this in the future

9. When testing is done, to push the device-specific tag merges to relevant repository HEAD's, run `aosp-merger/aosp-merger.sh submit-devices` - Please note this can only be done by Pixel device maintainers OR Global Committers and above

    NOTE: If you have your vendor repositories tracked somewhere you sync, you will also need to `cd` to those and `git push` them at this time by hand

10. Following the above, submit the kernel tag updates as well: `aosp-merger/aosp-merger.sh submit-kernels` - Please note this can only be done by Pixel device maintainers OR Global Committers and above

To merge a new CAF/CLO tag to all forked repositories:

1. Fetch the latest tags for supported SoCs and current version of QSSI from https://wiki.codelinaro.org/en/clo/la/release

2. Edit `vendor/lineage/vars/qcom`, `git commit` and upload the change to Gerrit

3. Run the merger script on whatever platforms you have updated the tags to create merges and upload them to Gerrit - e.g. To merge on all support platforms you'd run `for platform in qssi msm8953 sdm660 sdm845 msmnile kona lahaina waipio-vendor waipio-video; do aosp-merger/aosp-merger.sh clo $platform done`

4. When testing is done, a global committer or higher can run the merger script to push the merges to HEADs - e.g. To push aforementioned merges on all support platforms you'd run `for platform in qssi msm8953 sdm660 sdm845 msmnile kona lahaina waipio-vendor waipio-video; do aosp-merger/aosp-merger.sh submit-clo $platform done`

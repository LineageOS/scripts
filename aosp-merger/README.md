## LineageOS Merger Scripts

### Variables

`${TOP}/vendor/lineage/vars/` - This directory stores all variables for repositories that have upstreams that are regularly merged.

Standard Variables:

`common` - Stores the following data:

* `os_branch` - Previous/current LineageOS version
* `{prev_,}common_aosp_tag` - Previous/current tracked AOSP tag
* `topic` - The name of the topic to be used when pushing merges of newer tags to [Gerrit](https://review.lineageos.org) for review before merging

Special Variables:

`$platformName` - e.g. `qcom` - These files store tags specific to relevant non-AOSP repositories where upstream repos are regularly merged, such as CAF/CLO repositories.

* e.g. `qcom` - Stores names of relevant SoC platforms mapped to the tag we currently track for that platform's repositories

### Workflows

To merge a new AOSP tag platform-wide:

1. Wait for AOSP tags to show in https://android.googlesource.com/platform/manifest/

2. Edit `${TOP}/.repo/manifests/default.xml` with the new main tag

3. Upload `LineageOS/android` change generated to [Gerrit](https://review.lineageos.org)

4. Execute `repo sync` on the working tree

5. Edit `${TOP}/vendor/lineage/vars/common` moving the currently tracked tag from `common_aosp_tag` to `prev_common_aosp_tag`, then updating `common_aosp_tag` to reflect the newly tracked tag - lastly, update the `topic` variable to reflect the current month

6. Run `aosp-merger/aosp-merger.sh`, this will take some time, and reads all the variables you set up above while merging the new tags to all relevant tracked repos. This will likely create conflicts on some forked repository, and will ask you to resolve them. It will then issue a final check to ask you if you'd like to upload the merge to gerrit, then after approval uploads the merge to Gerrit for review.

7. Once testing of the merge is completed, a global committer or higher can run `aosp-merger/aosp-merger.sh submit-platform` to push the merge of the new tag to the HEAD of all relevant forked repositories

8. Directly after `submit-platform` is run, a Project Director must merge the `LineageOS/android` change on Gerrit uploaded as part of step 6 above

To merge a new CAF/CLO tag to all forked repositories:

1. Fetch the latest tags for supported SoCs and current version of QSSI from https://wiki.codelinaro.org/en/clo/la/release

2. Edit `vendor/lineage/vars/qcom`, `git commit` and upload the change to Gerrit

3. Run the merger script on whatever platforms you have updated the tags to create merges and upload them to Gerrit - e.g. To merge on all support platforms you'd run `for platform in qssi msm8953 sdm660 sdm845 msmnile kona lahaina waipio-vendor waipio-video; do aosp-merger/aosp-merger.sh clo $platform done`

4. When testing is done, a global committer or higher can run the merger script to push the merges to HEADs - e.g. To push aforementioned merges on all support platforms you'd run `for platform in qssi msm8953 sdm660 sdm845 msmnile kona lahaina waipio-vendor waipio-video; do aosp-merger/aosp-merger.sh submit-clo $platform done`

# Rough workflow

1. Snapshot the names of your current working branches to `branches.list` file:

       ./lineage/scripts/aosp-merger/branches_save.sh

2. Note current aosp tag in `.repo/manifests/default.xml`, update it to desired new tag and then create a local commit for the change (aosp-merger script checks for any uncommitted changes in the `.repo/manifests` git repo).
3. Create a staging branch and merge in the new AOSP tag:

       ./lineage/scripts/aosp-merger/aosp-merger.sh merge \<oldaosptag> \<newaosptag>
   (where oldaosptag is the original AOSP tag that was in `.repo/manifests/default.xml`)
   * Example invocation:

         ./lineage/scripts/aosp-merger/aosp-merger.sh merge android-8.0.0_r3 android-8.0.0_r30

4. Every project in your tree should now be one of:
   * \<newaosptag> if the project was tracking AOSP
   * a staging branch if the project was a fork from AOSP (check `merged_repos.txt` for status and whether there are conflicts to resolve)
   * the default repo lineage branch for `.repo/manifests/snippets.xml` projects
5. Restore your local branches and merge in the staging branch:

       ./lineage/scripts/aosp-merger/branches_rebase.sh \<nameofstagingbranch>
   * Example invocation:

         ./lineage/scripts/aosp-merger/branches_rebase.sh staging/lineage-15.0_merge-android-8.0.0_r30
6. Build, install, boot, verify, etc.

# TODO

* Make it work for rebase (I'm sure it'll need fixups).
* Instead of merging the staging branch into your local branch (if you have one), create a new branch for the local+staging merge.

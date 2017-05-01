# LineageOS Push Script

Pushes a local git repository's changes to Gerrit for code review

```
Usage:
  ./lineage-push.sh [options] branch

  Options:
    -d Upload change as draft.
    -e Update change as edit.
    -f Force push.
    -l <label> Assign label.
    -m Bypass review and merge.
    -r <ref> Push to specified ref ( will override draft ).
    -s Submit.
    -t <topic> Append topic to change.

  Example:
    lineage-push -d -t test cm-14.1
    lineage-push -s -l "Code-Review+2,Verified+1" cm-14.1
```

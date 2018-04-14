# LineageOS Push Script

```
usage: lineage-push.py [-h] [-d] [-e] [-f] [-l LABEL] [-m] [-p [PRIVATE]]
                       [-r REF] [-s] [-t TOPIC]
                       branch

Pushes a local git repository's changes to Gerrit for code review

positional arguments:
  branch                upload change to branch

optional arguments:
  -h, --help            show this help message and exit
  -d, --draft           upload change as draft
  -e, --edit            upload change as edit
  -f, --force           force push
  -l LABEL, --label LABEL
                        assign label
  -m, --merge           bypass review and merge
  -p [PRIVATE], --private [PRIVATE]
                        upload change as private
  -r REF, --ref REF     push to specified ref
  -s, --submit          submit change
  -t TOPIC, --topic TOPIC
                        append topic to change
```
```
  Examples:
    lineage-push -d -t test cm-14.1
    lineage-push -s -l "Code-Review+2,Verified+1" cm-14.1
```

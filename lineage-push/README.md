# LineageOS Push Script

Pushes a local git repository's changes to Gerrit for code review

```
usage: lineage-push.py [-h] [-b] [-d] [-e] [-f] [-l LABEL] [-m [MESSAGE]]
                       [-p [PRIVATE]] [-r REF] [-s] [-t TOPIC] [-w [WIP]]
                       branch

Pushes a local git repository's changes to Gerrit for code review

positional arguments:
  branch                upload change to branch

optional arguments:
  -h, --help            show this help message and exit
  -b, --bypass          bypass review and merge
  -d, --draft           upload change as draft
  -e, --edit            upload change as edit
  -f, --force           force push
  -l LABEL, --label LABEL
                        assign label
  -m [MESSAGE], --message [MESSAGE]
                        add message to change
  -p [PRIVATE], --private [PRIVATE]
                        upload change as private
  -r REF, --ref REF     push to specified ref
  -s, --submit          submit change
  -t TOPIC, --topic TOPIC
                        append topic to change
  -w [WIP], --wip [WIP]
                        upload change as WIP
```
```
  Examples:
    lineage-push -d -t test cm-14.1
    lineage-push -s -l "Code-Review+2,Verified+1" cm-14.1
```

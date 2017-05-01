#!/bin/bash

usage() {
    echo "Usage:"
    echo "  lineage-push [options] branch"
    echo
    echo "  Options:"
    echo "    -d Upload change as draft."
    echo "    -e Update change as edit."
    echo "    -f Force push."
    echo "    -l <label> Assign label."
    echo "    -m Bypass review and merge."
    echo "    -r <ref> Push to specified ref ( will override draft )."
    echo "    -s Submit."
    echo "    -t <topic> Append topic to change."
    echo
    echo "  Example:"
    echo "    lineage-push -d -t test cm-14.1"
    echo "    lineage-push -s -l \"Code-Review+2,Verified+1\" cm-14.1"
    echo
    exit 1
}

while getopts ":del:fmr:st:" opt; do
    case $opt in
        d) [ -z "$ref" ] && ref="refs/drafts/" ;;
        e) edit="%edit" ;;
        f) push_args="-f" ;;
        l) i=0
           labels="%"
           IFS=',' read -ra LABELS <<< "$OPTARG"
           for label in "${LABELS[@]}"; do
               labels+="l=$label"
               i=$(($i + 1))
               if [ $i -ne ${#LABELS[@]} ]; then
                   labels+=","
               fi
           done
           ;;
        m) [ -z "$ref" ] && ref="" ;;
        r) ref="refs/$OPTARG/" ;;
        s) submit="%submit" ;;
        t) topic="%topic=$OPTARG" ;;
        :)
          echo "Option -$OPTARG requires an argument"
          echo
          usage
          ;;
        \?)
          echo "Invalid option: -$OPTARG"
          echo
          usage
          ;;
    esac
done
shift $((OPTIND-1))

if [ "$#" -ne 1 ]; then
    usage
fi

if [ -z "$ref" ]; then
    ref="refs/for/"
fi

repo_name=$(git remote -v | grep LineageOS | head -n1 | awk '{print $2}' | sed 's/.*\///' | sed 's/\.git//')
username=$(git config review.review.lineageos.org.username)

git push ${push_args} ssh://${username}@review.lineageos.org:29418/LineageOS/${repo_name} HEAD:${ref}$1${topic}${labels}${submit}${edit}

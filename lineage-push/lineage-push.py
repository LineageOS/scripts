#!/usr/bin/env python

from __future__ import print_function

import re
import subprocess
import sys
from argparse import ArgumentParser


def push(args):
    command = 'git push'
    if args.force:
        command += ' -f'

    username = subprocess.check_output(
        ["git", "config", "review.review.lineageos.org.username"]).decode("utf-8").strip()
    remotes = subprocess.check_output(
        ["git", "remote", "-v"]).decode("utf-8").strip()
    repo = re.search(r'LineageOS\S+', remotes).group(0)

    command += ' ssh://{}@review.lineageos.org:29418/{}'.format(
        username, repo)
    command += ' HEAD:'

    if args.ref != 'for':
        command += 'refs/{}/'.format(args.ref)
    elif args.merge:
        command += ''
    elif args.draft:
        command += 'refs/drafts/'
    else:
        command += 'refs/{}/'.format(args.ref)

    command += args.branch

    if args.label:
        labels = args.label.split(',')
        command += '%'
        for count, label in enumerate(labels):
            command += 'l={}'.format(label)
            if count != len(labels) - 1:
                command += ','

    if args.edit:
        command += '%edit'

    if args.topic:
        command += '%topic={}'.format(args.topic)

    if args.submit:
        command += '%submit'

    sys.exit(subprocess.call(command, shell=True))


def parse_cmdline():
    parser = ArgumentParser(
        description='Pushes a local git repository\'s changes to Gerrit for code review')
    parser.add_argument('branch', help='upload change to branch')
    parser.add_argument('-d', '--draft', action='store_true',
                        help='upload change as draft')
    parser.add_argument('-e', '--edit', action='store_true',
                        help='upload change as edit')
    parser.add_argument(
        '-f', '--force', action='store_true', help='force push')
    parser.add_argument('-l', '--label', help='assign label')
    parser.add_argument('-m', '--merge', action='store_true',
                        help='bypass review and merge')
    parser.add_argument(
        '-r', '--ref', help='push to specified ref', default="for")
    parser.add_argument(
        '-s', '--submit', action='store_true', help='submit change')
    parser.add_argument('-t', '--topic', help='append topic to change')
    return parser.parse_args()


def main():
    args = parse_cmdline()
    push(args)


if __name__ == '__main__':
    main()

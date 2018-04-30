#!/usr/bin/env python

from __future__ import print_function

import re
import subprocess
import sys
from argparse import ArgumentParser, ArgumentTypeError

try:
    from urllib.parse import quote_plus
except ImportError:
    from urllib import quote_plus


def push(args):
    command = 'git push'
    if args.force:
        command += ' -f'

    username = subprocess.check_output(
        ["git", "config", "review.review.lineageos.org.username"]).decode("utf-8").strip()
    remotes = subprocess.check_output(
        ["git", "remote", "-v"]).decode("utf-8").strip()
    if "github.com/LineageOS" in remotes:
        repo = re.search(r'LineageOS\S+', remotes).group(0)
    elif "android.googlesource.com" in remotes:
        repo = re.search(r'platform\S+', remotes).group(0)
        repo = repo.replace("/", "_").replace("platform", "LineageOS/android")

    command += ' ssh://{}@review.lineageos.org:29418/{}'.format(
        username, repo)
    command += ' HEAD:'

    if args.ref != 'for':
        command += 'refs/{}/'.format(args.ref)
    elif args.bypass:
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

    if args.hashtag:
        command += '%hashtag={}'.format(args.hashtag)

    if args.submit:
        command += '%submit'

    if args.private == True:
        command += '%private'
    elif args.private == False:
        command += '%remove-private'

    if args.wip == True:
        command += '%wip'
    elif args.wip == False:
        command += '%ready'

    if args.message:
        command += '%m={}'.format(quote_plus(args.message))

    sys.exit(subprocess.call(command.split(' ')))


def str2bool(v):
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise ArgumentTypeError('Boolean value expected.')


def parse_cmdline():
    parser = ArgumentParser(
        description='Pushes a local git repository\'s changes to Gerrit for code review')
    parser.add_argument('branch', help='upload change to branch')
    parser.add_argument('-a', '--hashtag', action='store_true',
                        help='add hashtag to change')
    parser.add_argument('-b', '--bypass', action='store_true',
                        help='bypass review and merge')
    parser.add_argument('-d', '--draft', action='store_true',
                        help='upload change as draft')
    parser.add_argument('-e', '--edit', action='store_true',
                        help='upload change as edit')
    parser.add_argument(
        '-f', '--force', action='store_true', help='force push')
    parser.add_argument('-l', '--label', help='assign label')
    parser.add_argument('-m', '--message', nargs='?',
                        help='add message to change')
    parser.add_argument('-p', '--private', type=str2bool, nargs='?',
                        const=True, help='upload change as private')
    parser.add_argument(
        '-r', '--ref', help='push to specified ref', default="for")
    parser.add_argument(
        '-s', '--submit', action='store_true', help='submit change')
    parser.add_argument('-t', '--topic', help='append topic to change')
    parser.add_argument('-w', '--wip', type=str2bool, nargs='?',
                        const=True, help='upload change as WIP')
    return parser.parse_args()


def main():
    args = parse_cmdline()
    push(args)


if __name__ == '__main__':
    main()

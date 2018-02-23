#!/usr/bin/env python

import argparse
import json
import os
import re
import requests
import sys
from pygerrit2.rest import GerritRestAPI
from requests.auth import HTTPBasicAuth

u = ""
p = ""

review = "review.lineageos.org"
url = "https://" + review

f = open(os.getenv("HOME") + "/.gerritrc", "r")
for line in f:
  parts = line.rstrip().split("|")
  if parts[0] == review:
    u = parts[1]
    p = parts[2]

if u == "" or p == "":
  print("Couldn't find a valid config for " + review + " in " + os.getenv("HOME") + "/.gerritrc")
  sys.exit(0)

auth = HTTPBasicAuth(username=u, password=p)
gerrit = GerritRestAPI(url=url, auth=auth)

label_map = {'cr': 'Code-Review', 'v': 'Verified'}

parser = argparse.ArgumentParser()
parser.add_argument('--topic', '-t', metavar='topic', default=[], action='append', nargs='+', help='Topic(s) to process', dest='topic_raw')
parser.add_argument('--number', '-n', metavar='change_number', default=[], action='append', nargs='+', help='Change number(s) or range of numbers to process', dest='number_raw')
parser.add_argument('--steps', '-s', metavar='actions', default=[], action='append', nargs='+', help='Action(s) to perform, such as label+2, otherlabel-1, submit, abandon', dest='steps_raw', required=True)
args = parser.parse_args()

# Collapse nested lists
numbers = [item for sublist in args.number_raw for item in sublist]
topics = [item for sublist in args.topic_raw for item in sublist]
steps = [item for sublist in args.steps_raw for item in sublist]
# Expand comma separated string list elements
numbers = [item for sublist in numbers for item in sublist.split(',')]
topics = [item for sublist in topics for item in sublist.split(',')]
steps = [item for sublist in steps for item in sublist.split(',')]

if not topics and not numbers:
    print('Please specify a change number or topic')
    sys.exit(1)
if not steps:
    print('Please specify steps to perform on given changes')
    sys.exit(1)

def build_query(prefixes, topics, numbers):
    query = '?q=('
    if prefixes:
        query += "+AND+".join(prefixes) + ")+AND+("
    if topics:
        query += 'topic:' + '+OR+topic:'.join(topics)
    for number in numbers:
        if '-' in number:
            tmplist = number.split('-')
            new_numbers = list(str(x) for x in list(range(int(tmplist[0]), int(tmplist[1]) + 1)))
            numbers.remove(number)
            numbers.extend(new_numbers)
    if numbers:
        query += '+' + '+OR+'.join(numbers)
    return query + ')'

def apply_labels(change_number, labels):
    j = {}
    j['labels'] = labels
    return gerrit.post('/changes/{}/revisions/current/review'.format(change_number), json=j)

def submit(change_number, rebase=False):
    # rebase bool is currently unused
    return gerrit.post('/changes/{}/submit'.format(change_number))

def abandon(change_number):
    return gerrit.post('/changes/{}/abandon'.format(change_number))

def restore(change_number):
    return gerrit.post('/changes/{}/restore'.format(change_number))

def get_change_list(query):
    return gerrit.get('/changes/' + query)

print("Fetching info...")
query = build_query([], topics, numbers)
commits = get_change_list(query)
for commit in commits:
    print('  {}: [{}]: {}'.format(commit['_number'], commit['status'].capitalize(), commit['subject']))
print("About to follow plan ({}) on {} commits".format(",".join(steps), len(commits)))

try: input = raw_input
except NameError: pass
i = input("Is this okay? [y/N] ")
if i != 'y':
    print("Abort")
    sys.exit(1)

for s in steps:
    for commit in commits:
        if s == 'abandon':
            print("Abandoning {}".format(commit['_number']))
            abandon(commit['_number'])
        elif s == 'restore':
            print("Restoring {}".format(commit['_number']))
            restore(commit['_number'])
        elif s == 'submit':
            print("Submitting {}".format(commit['_number']))
            submit(commit['_number'])
        elif s == 'publish':
            print("Publishing {}".format(commit['_number']))
            submit(commit['_number'])
        elif s == 'approve':
            print("Approving {}".format(commit['_number']))
            apply_labels(commit['_number'], {'Code-Review': '+2', 'Verified': '+1'})
        elif s == 'block':
            print("Blocking {}".format(commit['_number']))
            apply_labels(commit['_number'], {'Code-Review': '-2', 'Verified': '-1'})
        elif len(re.split('([-+])', s)) == 3:
            l = re.split('([-+])', s)
            print("Applying {} to {}".format(label_map[l[0]]+l[1]+l[2], commit['_number']))
            apply_labels(commit['_number'], {label_map[l[0]]: l[1]+l[2]})

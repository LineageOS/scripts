#!/usr/bin/env python
#
# fuckit.py
# v1.7.2
#
# Written by Dan Pasanen, 2016
# WTFPL
#
# CHANGES
# v1.0 - initial release
# v1.1 - add support for a range of changes to ship
# v1.2 - add support for shipping a topic
# v1.3 - add error handling
# v1.4 - https
# v1.5 - print out the commit subject(s) and prompt user to verify
# v1.6 - python3 compat
# v1.7 - show commit status in list
# v1.7.1 - LineageOS
# v1.7.2 - Changed to fuckit (harryyoud)
#
# IMPORTANT:
# Must have a ~/.gerritrc with your gerrit info, pipe-separated
# Example:
#   review.lineageos.org|invisiblek|your_http_password_here
#   (get http password from your settings in gerrit's web interface)
#
# USAGE:
#  Any usage method can be used in conjunction with any other simply by
#    separating them by spaces. Order doesn't matter.
#
#  fuckit.py 123456                  (fuck over a single commit)
#  fuckit.py 123456 123457           (fuck over multiple commits)
#  fuckit.py 123456-123460           (fuck over a range of commits)
#  fuckit.py -t m7-audio-hal         (fuck over a topic)
#

import json
import os
import requests
import sys
from requests.auth import HTTPDigestAuth

u = ""
p = ""

# This could be changed or parameterized
review = "review.lineageos.org"
url = "https://" + review + "/a/changes/"

f = open(os.getenv("HOME") + "/.gerritrc", "r")
for line in f:
  parts = line.rstrip().split("|")
  if parts[0] == review:
    u = parts[1]
    p = parts[2]

if u == "" or p == "":
  print("Couldn't find a valid config for " + review + " in " + os.getenv("HOME") + "/.gerritrc")
  sys.exit(0)

auth = HTTPDigestAuth(username=u, password=p)

force = False

params = sys.argv
params.pop(0)
wasTopic = False
changes = []
for i, p in enumerate(params):
  if wasTopic:
    wasTopic = False
  elif p == "-t":
    wasTopic = True
    topic = params[i + 1]
    response = requests.get(url + "?q=topic:" + topic, auth=auth)
    j = json.loads(response.text[5:])
    for k in j:
      changes.append(str(k['_number']))
  elif p == "-f":
    force = True
  elif '-' in p:
    templist = p.split('-')
    for i in range(int(templist[0]), int(templist[1]) + 1):
      changes.append(str(i))
  else:
    changes.append(p)

if len(changes) < 1:
  print("Yea....if you could just go ahead and specify some commits, that'd be greaaaat.")
  sys.exit()

print("Fetching info about " + str(len(changes)) + " commits...\n")
messages = []

for c in changes:
  try:
    response = requests.get(url  + c + "/detail/", auth=auth)
    if response.status_code != 200:
      print("Could not fetch commit information")
      sys.exit()
    else:
      j = json.loads(response.text[5:])
      messages.append("[" + j['status'] + "]  " + j['subject'])
  except:
    sys.exit()

for m in messages:
  print(m)

if not force:
  try: input = raw_input
  except NameError: pass
  i = input("\nAbout to fuck over the preceeding commits. You good with this? [y/N] ")

  if i != 'y':
    print("Cancelled...")
    sys.exit()

for c in changes:
  # -2 it
  j = {}
  j['labels'] = {}
  j['labels']['Code-Review'] = "-2"
  j['labels']['Verified'] = "-1"
  response = requests.post(url + c + "/revisions/current/review", auth=auth, json=j)
  if response.status_code != 200:
    print("Failed to fuck over change " + c + " with error " + str(response.status_code) + ": " + response.text.rstrip())
    sys.exit(0)

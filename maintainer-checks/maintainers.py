#!/usr/bin/python3

import yaml
import re
import os
import json

mydir = os.path.dirname(os.path.abspath(__file__))

# Paths to certain repos
repo = {
    "updater": "../../updater",
    "wiki": "../../wiki",
    "hudson": "../../jenkins",
    "cve": "../../cve"
}

# List of all codenames in hudson
codenames = []
# List of devices in cve tracker
cve_entries = []
# List of devices with updater pages
updater_pages = []

# Open file and input lines as items in list
hudson_file = os.path.join(mydir, repo["hudson"] + "/lineage-build-targets")
with open(hudson_file) as f:
    for line in f:
        # Ignore blank lines or lines with comments
        if re.match(r"^\s*$", line) or re.match(r"#", line):
            continue
        # Add codenames to list
        codenames.append(re.sub(r" .*", "", line.strip()))

# Sort codenames alphabetically
codenames.sort()

# Create list of devices in cve tracker
cve_json_file = os.path.join(mydir, repo["cve"] + "/kernels.json")
with open(cve_json_file) as f:
    json_file = json.load(f)

for kernel in json_file:
    for device in json_file[kernel]:
        device = re.sub(r"android_device_[a-zA-Z0-9]*_", "", device)
        cve_entries.append(device)

# CVE tracker checking
for codename in codenames:
    if codename not in cve_entries:
        print("{} doesn't have an entry in the CVE tracker".format(codename))

# Create list of updater pages
updater_json_file = os.path.join(mydir, repo["updater"] + "/devices.json")
with open(updater_json_file) as f:
    json_file = json.load(f)
for device in json_file:
    updater_pages.append(device["model"])

# Updater checking
for codename in codenames:
    if codename not in updater_pages:
        print("{} doesn't have an updater page".format(codename))

# Wiki checking
for codename in codenames:
    wiki_yml_file = os.path.join(mydir, repo["wiki"] + "/_data/devices/" + codename + ".yml")
    if not os.path.isfile(wiki_yml_file):
        print("{} doesn't have a wiki page".format(codename))
        continue
    with open(wiki_yml_file) as f:
        yml = yaml.load(f)
    try:
        if not yml["maintainers"]:
            print("{} doesn't have a maintainer listed".format(codename))
    except KeyError:
        print("{} doesn't have a maintainers field".format(codename))
    try:
        if not yml["install_method"] or "TODO" in yml["install_method"]:
            print("{} doesn't have an install method listed".format(codename))
        if "dd" in yml["install_method"]:
            try:
                if not yml["recovery_partition"]:
                    print("{} doesn't have a recovery partition listed".format(codename))
            except KeyError:
                print("{} doesn't have a recovery partition field".format(codename))
            try:
                if not yml["root_method"]:
                    print("{} doesn't have a root method listed".format(codename))
            except KeyError:
                print("{} doesn't have a root method field".format(codename))
    except KeyError:
        print("{} doesn't have an install method field".format(codename))

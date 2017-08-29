#!/usr/bin/python3

import yaml
import re
import os
import json
import argparse

mydir = os.path.dirname(os.path.abspath(__file__))

parser = argparse.ArgumentParser()
parser.add_argument('-m', '--maintainers', help='list maintainers for devices', action='store_true', required=False)
parser.add_argument('-j', '--jira', dest="jira_file", required=False, help='Path to list of jira developers', metavar='FILE')
args = parser.parse_args()

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
# List of jira developers
jira_devs = []
# Discontinued devices
discontinued_devices = []

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

# Wiki checking
for codename in codenames:
    wiki_yml_file = os.path.join(mydir, repo["wiki"] + "/_data/devices/" + codename + ".yml")
    try:
        with open(wiki_yml_file) as f:
            yml = yaml.load(f)
    except FileNotFoundError:
        print("{} doesn't have a wiki page".format(codename))
        continue
    try:
        if not yml["maintainers"]:
            print("{} doesn't have a maintainer listed".format(codename))
    except KeyError:
        print("{} doesn't have a maintainers field".format(codename))
    try:
        if not yml["install_method"]:
            print("{} doesn't have an install method listed".format(codename))
        elif "fastboot_generic" in yml["install_method"]:
            print("{} uses fastboot_generic install method".format(codename))
        elif "dd" in yml["install_method"]:
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
    try:
        if yml["twrp_site"]:
            print("{} uses unofficial TWRP".format(codename))
    except KeyError:
        pass

wiki_yml_dir = os.path.join(mydir, repo["wiki"] + "/_data/devices")
for wiki_yml in os.listdir(wiki_yml_dir):
    codename = re.sub(r"\.yml", "", wiki_yml.strip())
    if codename not in codenames:
        wiki_yml_file = os.path.join(mydir, repo["wiki"] + "/_data/devices/" + wiki_yml)
        with open(wiki_yml_file) as f:
            yml = yaml.load(f)
            if "discontinued" not in yml["channels"]:
                print("{} has a wiki page but isn't in hudson".format(codename))
            else:
                discontinued_devices.append(codename)

# Updater checking
for codename in codenames:
    if codename not in updater_pages:
        print("{} doesn't have an updater page".format(codename))

for codename in updater_pages:
    if codename not in codenames and codename not in discontinued_devices:
         print("{} has an updater page but is not in hudson".format(codename))

# Optionally print out all maintainer info
if args.maintainers:
    print("---------------MAINTAINER INFO DUMP---------------")
    for codename in codenames:
        wiki_yml_file = os.path.join(mydir, repo["wiki"] + "/_data/devices/" + codename + ".yml")
        toprint = "{}:".format(codename)
        try:
            with open(wiki_yml_file) as f:
                yml = yaml.load(f)
        except FileNotFoundError:
            # Skip devices without wiki pages, we already errored about it
            continue
        try:
            for maintainer in yml["maintainers"]:
                toprint += ", {}".format(maintainer)
        except KeyError:
            # Skip devices without maintainer fields, we already errored about it
            continue
        print(toprint.replace(":,", ":"))

if args.jira_file:
    with open(args.jira_file) as f:
        for line in f:
            jira_devs.append(line.strip())
    for codename in codenames:
        wiki_yml_file = os.path.join(mydir, repo["wiki"] + "/_data/devices/" + codename + ".yml")
        try:
            with open(wiki_yml_file) as f:
                yml = yaml.load(f)
        except FileNotFoundError:
            # Skip devices without wiki pages, we already errored about it
            continue
        try:
            for maintainer in yml["maintainers"]:
                if maintainer not in jira_devs:
                    print("{} is listed as a maintainer for {} but doesn't have a jira developer account".format(maintainer, codename))
        except KeyError:
            # Skip devices without maintainer fields, we already errored about it
            continue

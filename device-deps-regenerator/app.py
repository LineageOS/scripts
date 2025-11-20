# SPDX-FileCopyrightText: 2017-2023 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

import argparse
import concurrent.futures
import json
import requests
import subprocess
import traceback

from xml.etree import ElementTree

parser = argparse.ArgumentParser()
parser.add_argument(
    "-j", "--jobs", type=int, help="Max number of workers to use. Default is none"
)
args = parser.parse_args()

# supported branches, newest to oldest
CUR_BRANCHES = ["lineage-23.1", "lineage-23.0", "lineage-22.2", "lineage-22.1", "lineage-21", "lineage-21.0", "lineage-20", "lineage-20.0", "lineage-19.1", "lineage-18.1"]


def get_cm_dependencies(name):
    try:
        stdout = subprocess.run(
            ["git", "ls-remote", "-h", f"https://:@github.com/LineageOS/{name}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout.decode()
        branches = [x.split()[-1] for x in stdout.splitlines()]
    except:
        return None

    branch = next((x for x in CUR_BRANCHES if f"refs/heads/{x}" in branches), None)

    if branch is None:
        return None

    try:
        cmdeps = requests.get(
            f"https://raw.githubusercontent.com/LineageOS/{name}/{branch}/lineage.dependencies"
        ).json()
    except:
        cmdeps = []

    mydeps = []
    non_device_repos = set()
    for el in cmdeps:
        if el.get("remote", "github") != "github":
            continue
        if "_device_" not in el["repository"]:
            non_device_repos.add(el["repository"])
        depbranch = el.get("branch", branch)
        mydeps.append({"repo": el["repository"], "branch": depbranch})

    return [mydeps, non_device_repos]


futures = {}
n = 1

dependencies = {}
other_repos = set()

with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
    elements = ElementTree.fromstring(
        requests.get(
            "https://raw.githubusercontent.com/LineageOS/mirror/main/default.xml"
        ).text
    )

    for name in [
        x.attrib["name"].split("/", maxsplit=1)[-1]
        for x in elements.findall(".//project")
    ]:
        if "_device_" not in name and "_hardware_" not in name:
            continue
        print(n, name)
        n += 1
        futures[executor.submit(get_cm_dependencies, name)] = name
    for future in concurrent.futures.as_completed(futures):
        name = futures[future]
        try:
            data = future.result()
            if data is None:
                continue
            dependencies[name] = data[0]
            other_repos.update(data[1])
            print(name, "=>", data[0])
        except Exception as e:
            print(f"{name!r} generated an exception: {e}")
            traceback.print_exc()
            continue
    futures = {}

    print(other_repos)
    for name in other_repos:
        print(name)
        try:
            futures[executor.submit(get_cm_dependencies, name)] = name
        except Exception:
            continue

    other_repos = set()
    for future in concurrent.futures.as_completed(futures):
        name = futures[future]
        try:
            data = future.result()
            if data is None:
                continue
            dependencies[name] = data[0]
            for el in data[1]:
                if el in dependencies:
                    continue
                other_repos.update(data[1])
            print(name, "=>", data[0])
        except Exception as e:
            print(f"{name!r} generated an exception: {e}")
            traceback.print_exc()
            continue
    futures = {}


print(other_repos)

with open("out.json", "w") as f:
    json.dump(dependencies, f, indent=4)

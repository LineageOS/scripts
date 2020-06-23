#!/usr/bin/env python

import requests

GITLAB_TOKEN = os.environ.get("GITLAB_TOKEN", None)
headers = {"Private-Token": config.GITLAB_TOKEN}

project = 9202919
api_url = f"https://gitlab.com/api/v4/projects/{project}"
issues_url = f"{api_url}/issues"

def post_reply(iid, reply):
    resp = requests.post(f"{issues_url}/{iid}/notes", json={"body": "\n".join(reply)}, headers=headers)
    if resp.status_code != 201:
        print(f"Error replying - ${resp.json()}")


def edit_issue(iid, edits):
    resp = requests.put(f"{issues_url}/{iid}", json=edits, headers=headers)
    if resp.status_code != 200:
        print(f"Error updating issue - ${resp.json()}")


def close_unmaintained(device):
    for device in unmaintained:
        print(f"Closing issues for unmaintained device '{device}'")
        page = 1
        while True:
            url = f"{issues_url}?state=opened&labels=device:{device}&per_page=100&pag={page}"
            resp = requests.get(url, headers=headers)
            if resp.status_code != 200:
                print(f"Error retrieving issues - {resp.json()}")
                exit()

            response = resp.json()
            if not response:
                break

            for issue in response:
                if "platform" in issue['labels'] or "platform-atv" in issue['labels']:
                    continue
                reply = [
                    "Hi!\n",
                    "Thank you for reporting!\n"
                    "In an attempt to clean up, I am closing all issues for devices that are currently not receiving builds.\n",
                    "\n",
                    "- This action was performed by a script"
                ]
                close_issue(issue, reply)

            page = page + 1


def close_issues_on_old_branches(maintained):
    for device in maintained:
        print(f"Closing issues for maintained device '{device}'")
        current_branch = maintained[device]
        branch_label = f'version:{current_branch}'
        page = 1
        while True:
            url = f"{issues_url}?state=opened&labels=device:{device}&per_page=100&page={page}"
            resp = requests.get(url, headers=headers)
            if resp.status_code != 200:
                print(f"Error retrieving issues - {resp.json()}")
                exit()

            response = resp.json()
            if not response:
                break

            for issue in response:
                if "platform" in issue['labels'] or "platform-atv" in issue['labels'] or branch_label in issue['labels']:
                    continue
                reply = [
                    "Hi!\n",
                    "Thank you for reporting!\n"
                    "In an attempt to clean up, I am closing all issues reported against the non current build version for each device.\n",
                    f"If this issue still exists on '{current_branch}' please feel free to reopen this issue.\n",
                    "\n"
                    "- This action was performed by a script"
                ]
                close_issue(issue, reply)

            page = page + 1


def close_issue(issue, reply):
    post_reply(issue["iid"], reply)
    # edit issue
    edits = { }
    edits["state_event"] = "close"
    edit_issue(issue["iid"], edits)
    print(f"Closed #{issue['iid']} ({issue['web_url']})")


def get_device_labels():
    print("Reading issue labels from project");
    device_labels = []
    page = 1
    while True:
        resp = requests.get(f"{api_url}/labels?page={page}&per_page=100", headers=headers)
        if resp.status_code != 200:
            print(f"Error getting labels - {resp.json()}")
            exit()

        response = resp.json()
        if not response:
            break

        for label in response:
            if label['name'].startswith("device:"):
                device_labels.append(label['name'].split("device:")[1])

        page = page + 1

    return device_labels


def get_maintained_devices():
    print('Reading list of currently built devices')

    resp = requests.get("https://raw.githubusercontent.com/LineageOS/hudson/master/lineage-build-targets")
    if resp.status_code != 200:
        print(f"Error getting devices - {resp.json()}")
        exit()

    text = resp.text
    lines = text.split("\n")
    maintained = {}
    for line in lines:
        if line == '' or line.startswith("#"):
            continue;

        parts = line.split(" ")
        device = parts[0]
        branch = parts[2]
        maintained[device] = branch

    return maintained


def get_unmaintained_devices(device_labels, devices):
    print('Filtering for unmaintained device labels')

    unmaintained = []
    for label in device_labels:
        if not label in devices:
            unmaintained.append(label)

    return unmaintained


def check_issues_count(devices):
    count = 0
    for device in devices:
        url = f"{issues_url}?state=opened&labels=device:{device}&per_page=100"
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            print(f"Error getting devices - {resp.json()}")
            exit()

        respJson = resp.json()
        print(f'Found {len(respJson)} issues for {device}!');
        count = count + len(respJson)
    print(f'Total: {count} issues')


if __name__ == "__main__":
    if GITLAB_TOKEN is None:
        print("No GITLAB_TOKEN is set!")
        exit()

    devices_labels = get_device_labels()
    maintained = get_maintained_devices()
    unmaintained = get_unmaintained_devices(devices_labels, maintained)
    close_unmaintained(unmaintained)
    close_issues_on_old_branches(maintained)

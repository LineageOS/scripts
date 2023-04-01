import argparse
import concurrent.futures
import json
import requests
import traceback

from subprocess import Popen, PIPE
from xml.etree import ElementTree

parser = argparse.ArgumentParser()
parser.add_argument('-j', '--jobs', type=int, help='Max number of workers to use. Default is none')
args = parser.parse_args()

# supported branches, newest to oldest
CUR_BRANCHES = ['lineage-20', 'lineage-20.0', 'lineage-19.1', 'lineage-18.1']

def get_cm_dependencies(repo):
    p = Popen(['git', 'remote', 'show', f'git@github.com:LineageOS/{repo}.git'], stdout=PIPE)
    stdout, _ = p.communicate()
    try:
        branch = stdout.splitlines()[-1].split()[-1].decode()
    except:
        return None

    if branch not in CUR_BRANCHES:
        return None

    try:
        cmdeps = requests.get(f'https://raw.githubusercontent.com/LineageOS/{repo}/{branch}/lineage.dependencies').json()
    except:
        return None

    mydeps = []
    non_device_repos = set()
    for el in cmdeps:
        if '_device_' not in el['repository']:
            non_device_repos.add(el['repository'])
        depbranch = el.get('branch', branch)
        mydeps.append({'repo': el['repository'], 'branch': depbranch})

    return [mydeps, non_device_repos]

futures = {}
n = 1

dependencies = {}
other_repos = set()

with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
    req = requests.get('https://raw.githubusercontent.com/LineageOS/mirror/master/default.xml')
    elements = ElementTree.fromstring(req.text)
    repos = [x.attrib['name'][10:] for x in elements.findall('.//project')]

    for repo in repos:
        if '_device_' not in repo and '_hardware_' not in repo:
            continue
        print(n, repo)
        n += 1
        futures[executor.submit(get_cm_dependencies, repo)] = repo
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
            print('%r generated an exception: %s'%(name, e))
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
            print('%r generated an exception: %s'%(name, e))
            traceback.print_exc()
            continue
    futures = {}


print(other_repos)
#for name in other_repos:
#    repo = org.get_repo(name)
#    dependencies[name] = get_cm_dependencies(repo)

with open('out.json', 'w') as f:
    json.dump(dependencies, f, indent=4)

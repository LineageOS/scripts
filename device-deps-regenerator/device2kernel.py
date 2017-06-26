import json
with open('out.json') as f:
    mapping = json.load(f)

kernels = {}

reverse_deps = {device: [] for device in mapping}

for device in mapping:
    deps = mapping[device]['deps']

    for repo in deps:
        name = repo['repo']
        if len(repo['branch'].split('-')) > 2:
            name += '-' + '-'.join(repo['branch'].split('-')[2:])
        if name not in reverse_deps:
            reverse_deps[name] = []
        reverse_deps[name].append(device)

def simplify_reverse_deps(repo):
    if len(reverse_deps[repo]) == 0 and '-common' not in repo:
        return {repo,}
    res = set()
    for i in reverse_deps[repo]:
        res.update(simplify_reverse_deps(i))
    if repo in mapping and not mapping[repo]['common']:
        res.add(repo)
    return res

for repo in reverse_deps:
    if 'kernel' in repo:
        kernels[repo] = sorted(list(simplify_reverse_deps(repo)))

with open('kernels.json', 'w') as f:
    json.dump(kernels, f, indent=4, sort_keys=True)

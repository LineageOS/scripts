import json

with open("out.json") as f:
    mapping = json.load(f)

devices = {}
suffixes = {}
ignorelist = [
    "sepolicy",
    "devicesettings",
    "common",
    "atv",
    "redbull",
    "raviole",
    "gs101",
    "pantah",
    "gs201",
    "contexthub",
    "sm8450-devicetrees",
    "sm8550-devicetrees",
]


def simplify_reverse_deps(repo, device):
    # repo['branch'] = cm-14.1 or cm-14.1-caf or cm-14.1-sony
    if "branch" in repo and repo["branch"].count("-") > 1:  # get suffix
        if repo["repo"] not in suffixes:
            suffixes[repo["repo"]] = {}
        suffixes[repo["repo"]][device] = "-" + repo["branch"].split("-", 2)[2]

    if repo["repo"] not in mapping or len(mapping[repo["repo"]]) == 0:
        return [repo["repo"]]
    res = []
    for i in mapping[repo["repo"]]:
        res += simplify_reverse_deps(i, device)
    res.append(repo["repo"])
    return res


for repo in mapping:
    if "device" not in repo or any(x in repo for x in ignorelist):
        continue
    codename = repo.split("_", maxsplit=3)[-1]
    if codename in devices:
        print(f"warning: dupe: {codename}")
    devices[codename] = sorted(
        list(set(simplify_reverse_deps({"repo": repo}, codename)))
    )

with open("device_deps.json", "w") as f:
    out = {"devices": devices, "suffixes": suffixes}
    out = devices
    json.dump(out, f, indent=4, sort_keys=True)
    f.write("\n")

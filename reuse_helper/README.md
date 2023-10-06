# REUSE compliance converter

This script will try to parse and replace existing comments to the proper SPDX ones.

## Requirements

This requires the `pipx` package to be installed

## Usage

```
reuse_helper.py -p <project path>
```

Required arguments:\
  -p PROJECT, --project PROJECT     Specify the path of the project you want to convert (relative to lineage sources)

optional arguments:\
  -h, --help                        show this help message and exit
  -r ROOT, --root ROOT              Specify the root path of your sources

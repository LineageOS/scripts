#!/usr/bin/env python3
import argparse
import collections
import dataclasses
import glob
import pathlib
import subprocess
import textwrap

import yaml

CROOT = str(pathlib.Path(__file__).parents[3])


@dataclasses.dataclass
class WikiData:
    codename: str
    device_names: list
    maintainers: set
    versions: list

    def to_jekyll_table(self) -> str:
        return '| {} |'.format(' | '.join([
            ' / '.join(self.device_names),
            f'[{self.codename}](https://wiki.lineageos.org/devices/{self.codename})',
            ', '.join(self.maintainers),
            str(self.versions[-2]) if len(self.versions) > 1 else ''
        ]))


def get_build_targets(git_head: str) -> dict:
    build_targets = {}

    for line in subprocess.run(['git', 'show', f'{git_head}:lineage-build-targets'],
                               cwd=f'{CROOT}/lineage/hudson',
                               stdout=subprocess.PIPE).stdout.decode().splitlines():
        if line and not line.startswith('#'):
            device, build_type, version, cadence = line.split()
            build_targets[device] = version

    return build_targets


def get_wiki_data(codename: str) -> WikiData:
    device_names = []
    maintainers = []
    versions = []

    for path in glob.glob(f'{CROOT}/lineage/wiki/_data/devices/{codename}.yml') + glob.glob(
            f'{CROOT}/lineage/wiki/_data/devices/{codename}_variant*.yml'):
        doc = yaml.load(open(path, 'r').read(), Loader=yaml.SafeLoader)
        device_names.append(f'{doc["vendor"]} {doc["name"]}')
        maintainers = doc['maintainers']
        versions = doc['versions']

    return WikiData(codename, device_names, maintainers, versions)


def parse_cmdline() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Generate device table for the blog post')
    parser.add_argument('hudson_head_before', help='Hudson Git HEAD as of the previous changelog post')
    return parser.parse_args()


def main() -> None:
    args = parse_cmdline()

    build_targets_before = get_build_targets(args.hudson_head_before)
    build_targets_after = get_build_targets('HEAD')

    new_devices = collections.defaultdict(list)

    for codename, branch in build_targets_after.items():
        if build_targets_before.get(codename, None) != branch:
            new_devices[branch].append(codename)

    for branch, codenames in new_devices.items():
        _, version = branch.split('-')

        if version.endswith('.0'):
            version = version[:-2]

        print(textwrap.dedent(f'''\
            #### Added {version} devices

            {{: .table }}
            | Device name | Wiki | Maintainers | Moved from |
            |-------------|------|-------------|------------|'''))
        print('\n'.join(
            sorted([get_wiki_data(x).to_jekyll_table() for x in codenames])
        ))
        print()


if __name__ == '__main__':
    main()

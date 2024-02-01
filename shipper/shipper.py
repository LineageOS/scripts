import argparse
import dataclasses
import glob
import subprocess
import textwrap

import yaml


@dataclasses.dataclass
class WikiData:
    codename: str
    device_names: list
    maintainers: set
    versions: list

    def to_jekyll_table(self):
        return '| {} |'.format(' | '.join([
            ' / '.join(self.device_names),
            f'[{self.codename}](https://wiki.lineageos.org/devices/{self.codename})',
            ', '.join(self.maintainers),
            str(self.versions[-2]) if len(self.versions) > 1 else ''
        ]))


def fetch_build_targets(croot: str, git_head: str):
    build_targets = {}

    for line in subprocess.run(['git', 'show', f'{git_head}:lineage-build-targets'],
                               cwd=f'{croot}/lineage/hudson',
                               stdout=subprocess.PIPE).stdout.decode().splitlines():
        if ' lineage-' in line:
            codename, _, branch, _ = line.split()
            build_targets[codename] = branch

    return build_targets


def get_wiki_data(croot: str, codename: str):
    device_names = []
    maintainers = set()
    versions = []

    for path in glob.glob(f'{croot}/lineage/wiki/_data/devices/{codename}.yml') + glob.glob(
            f'{croot}/lineage/wiki/_data/devices/{codename}_variant*.yml'):
        doc = yaml.load(open(path, 'r').read(), Loader=yaml.FullLoader)
        device_names.append(f'{doc["vendor"]} {doc["name"]}')
        maintainers.update(set(doc['maintainers']))
        versions = doc['versions']

    return WikiData(codename, device_names, maintainers, versions)


def parse_cmdline():
    parser = argparse.ArgumentParser(description='Generate device table for blog post')
    parser.add_argument('croot',
                        help='Path to LineageOS source code checkout')
    parser.add_argument('hudson_head_before',
                        help='Hudson Git HEAD as of the previous changelog post')
    return parser.parse_args()


def main():
    args = parse_cmdline()

    build_targets_before = fetch_build_targets(args.croot, args.hudson_head_before)
    build_targets_after = fetch_build_targets(args.croot, 'HEAD')

    new_devices = {}

    for branch in sorted(set(build_targets_after.values())):
        new_devices[branch] = []

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
            sorted([get_wiki_data(args.croot, x).to_jekyll_table() for x in codenames])
        ), '\n')


if __name__ == '__main__':
    main()

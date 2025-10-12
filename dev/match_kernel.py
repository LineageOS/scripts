#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import subprocess
import xml.etree.ElementTree as ET
from argparse import ArgumentParser
from os import path
from pathlib import Path
from typing import Dict, Generator, Iterable, List, Optional, Tuple
from urllib.parse import urljoin

from utils.utils import Color, WorkingDirectory, color_print, run_cmd

REMOTE_NAME = 'origin'


class Config:
    def __init__(
        self,
        match_patterns: List[str],
        mirror: Optional[str],
    ):
        self.match_patterns = match_patterns
        self.mirror = mirror


def clean_repo():
    print('Cleaning...')
    run_cmd(['rm', '-rf', '.git'])


def init_repo(config: Config, project_name: str, remote_url: str):
    if config.mirror is None:
        project_url = urljoin(remote_url, project_name)
    else:
        project_url = path.join(config.mirror, f'{project_name}.git')

    print('Initializing...')
    run_cmd(['git', 'init'])
    try:
        run_cmd(['git', 'add', '.'])
        run_cmd(['git', 'commit', '-m', 'Initial commit'])
        run_cmd(['git', 'remote', 'add', REMOTE_NAME, project_url])
    except ValueError:
        pass


def fetch_remote(config: Config):
    configs: List[str] = []
    if config.mirror:
        configs.extend(['-c', 'safe.directory=*'])

    print('Fetching remote...')
    run_cmd(['git', *configs, 'fetch', REMOTE_NAME], capture=False)
    run_cmd(['git', *configs, 'fetch', '--tags', REMOTE_NAME], capture=False)


def ref_to_hash(ref: str):
    return run_cmd(['git', 'rev-parse', ref]).strip()


def list_matching_branches_tags(
    match_patterns: List[str],
) -> Generator[str, None, None]:
    proc = subprocess.Popen(
        [
            'git',
            'for-each-ref',
            # Sort in descending order of creation date
            '--sort=-creatordate',
            '--format=%(refname)',
            *match_patterns,
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    assert proc.stdout is not None
    for ref_line in proc.stdout:
        yield ref_line.strip()


def list_commits(ref: str) -> Generator[str, None, None]:
    proc = subprocess.Popen(
        ['git', 'rev-list', ref],
        stdout=subprocess.PIPE,
        text=True,
    )
    assert proc.stdout is not None
    for ref_line in proc.stdout:
        yield ref_line.strip()


def ref_matching_refs(match_ref: str):
    for ref in list_matching_branches_tags([]):
        ref_commit = ref_to_hash(ref)
        if ref_commit == match_ref:
            yield ref


def rebase_repo(base_ref: str):
    head_ref = ref_to_hash('HEAD')
    run_cmd(['git', 'checkout', base_ref])
    run_cmd(['git', 'read-tree', '--reset', '-u', head_ref])
    run_cmd(['git', 'add', '.'])
    run_cmd(['git', 'commit', '-m', 'Import changes'])


def compare_ref(ref: str):
    stats = run_cmd(
        [
            'git',
            'diff',
            '--shortstat',
            ref,
            'HEAD',
            '--',
            # Google seems to remove .gitignore from some directories
            ':(exclude).gitignore',
        ]
    ).strip()

    files_changed = insertions = deletions = 0
    for part in stats.split(','):
        part = part.strip()
        if 'file' in part:
            files_changed = int(part.split()[0])
        elif 'insertion' in part:
            insertions = int(part.split()[0])
        elif 'deletion' in part:
            deletions = int(part.split()[0])

    return files_changed + insertions + deletions


def match_refs(refs: Iterable[str], linear: bool = False):
    best_ref = None
    best_score = None
    last_score = None
    score = None
    for ref in refs:
        if ref == f'refs/remotes/{REMOTE_NAME}/HEAD':
            continue

        last_score = score
        score = compare_ref(ref)
        if linear and last_score is not None and score > last_score:
            break

        if best_score is None or best_score > score:
            best_score = score
            best_ref = ref

        if best_score == 0:
            break

    return best_ref, best_score


def find_best_branch_tag(match_patterns: List[str]):
    refs = list_matching_branches_tags(match_patterns)
    return match_refs(refs)


def find_best_commit(starting_ref: str):
    refs = list_commits(starting_ref)
    return match_refs(refs, True)


def match_project(config: Config, project_name: str, remote_url: str):
    clean_repo()
    init_repo(config, project_name, remote_url)
    fetch_remote(config)

    print('Finding best branch/tag...')
    best_ref, best_score = find_best_branch_tag(config.match_patterns)
    if best_ref is None:
        color_print('Failed to find best ref', color=Color.RED)
        return

    print(f'Found branch/tag: {best_ref}')
    best_ref = ref_to_hash(best_ref)

    if best_score != 0:
        print('Finding best commit...')
        best_ref, best_score = find_best_commit(best_ref)
        assert best_ref is not None

    if best_score != 0:
        print('Rebasing changes...')
        rebase_repo(best_ref)

        color_print(
            f'Closest commit: {best_ref}, diff: {best_score}',
            color=Color.YELLOW,
        )
    else:
        color_print(
            f'Matching commit: {best_ref}',
            color=Color.GREEN,
        )

    matching_refs = ref_matching_refs(best_ref)
    print('Matching refs:')
    for ref in matching_refs:
        print(ref)


def match_directory(
    config: Config,
    dir_path: str,
):
    aosp_manifest_path = Path(dir_path, 'aosp_manifest.xml')
    print(f'Parsing {aosp_manifest_path}')

    tree = ET.parse(aosp_manifest_path)
    root = tree.getroot()

    remote_map: Dict[str, str] = {}
    default_remote_name: Optional[str] = None
    default_revision: Optional[str] = None
    projects: List[Tuple[str, str, Optional[str]]] = []

    for child in root:
        if child.tag == 'remote':
            remote_map[child.attrib['name']] = child.attrib['fetch']

        if child.tag == 'default':
            default_remote_name = child.attrib['remote']
            default_revision = child.attrib['revision']

        if child.tag == 'project':
            if child.attrib['path'].startswith('private/'):
                continue

            project_remote_name = child.attrib.get('remote')
            project_rel_path = child.attrib['path']
            project_name = child.attrib['name']
            projects.append(
                (project_rel_path, project_name, project_remote_name)
            )

    assert default_remote_name is not None
    assert default_revision is not None

    color_print(f'Found revision: {default_revision}', color=Color.GREEN)
    print()

    for project_rel_path, project_name, project_remote_name in projects:
        if project_remote_name is None:
            project_remote_name = default_remote_name

        remote_url = remote_map[default_remote_name]

        print(
            f'Matching project path: {project_rel_path}, '
            f'name: {project_name}, '
            f'remote: {project_remote_name}'
        )

        project_path = Path(dir_path, project_rel_path)
        with WorkingDirectory(str(project_path)):
            match_project(config, project_name, remote_url)
            print()


def build_match_patterns(
    branch_globs: Optional[List[str]],
    tag_globs: Optional[List[str]],
):
    match_patterns: List[str] = []
    if branch_globs is None:
        branch_globs = ['*']

    for glob in branch_globs:
        branch_pattern = f'refs/remotes/{REMOTE_NAME}/{glob}'
        match_patterns.append(branch_pattern)

    if tag_globs is None:
        tag_globs = ['*']

    for glob in tag_globs:
        tag_pattern = f'refs/tags/{glob}'
        match_patterns.append(tag_pattern)

    return match_patterns


def match_kernel():
    parser = ArgumentParser(
        prog='match_kernel.py',
        description="Match Google's kernel release containing aosp_manifest.xml"
        'with public AOSP commits',
    )
    parser.add_argument(
        'dirs',
        type=str,
        nargs='+',
        help='Directory containing aosp_manifest.xml',
    )
    parser.add_argument(
        '-b',
        '--branch-glob',
        action='append',
        help='Glob pattern for matching branches',
    )
    parser.add_argument(
        '-t',
        '--tag-glob',
        action='append',
        help='Glob pattern for matching tags',
    )
    parser.add_argument('-m', '--mirror', help='Path to mirror')

    args = parser.parse_args()
    match_patterns = build_match_patterns(args.branch_glob, args.tag_glob)
    config = Config(match_patterns, args.mirror)

    for dir_path in args.dirs:
        match_directory(config, dir_path)


if __name__ == '__main__':
    match_kernel()

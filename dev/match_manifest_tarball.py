#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import fnmatch
import shutil
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
        output_dir: str,
        projects: List[str],
        excluded_projects: List[str],
        excluded_project_paths: List[str],
    ):
        self.match_patterns = match_patterns
        self.mirror = mirror
        self.output_dir = output_dir
        self.projects = projects
        self.excluded_projects = excluded_projects
        self.excluded_project_paths = excluded_project_paths


def init_repo(config: Config, project_name: str, remote_url: str):
    extra_args: List[str] = []
    project_url = urljoin(remote_url, project_name)
    if config.mirror is not None:
        reference_path = path.join(config.mirror, f'{project_name}.git')
        extra_args.extend(['--reference', reference_path])

    print('Initializing...')
    run_cmd(['git', 'clone', *extra_args, project_url, '.'])

    print('Fetching...')
    run_cmd(['git', 'fetch', '--all', '--tags'], capture=False)


def copy_tarball_to_repo(tarball_path: Path):
    run_cmd(['git', 'switch', '--orphan', 'tarball'])
    run_cmd(['rsync', '-a', "--exclude='.git'", f'{tarball_path}/', '.'])
    run_cmd(['git', 'add', '.'])
    run_cmd(['git', 'commit', '-m', 'Initial commit'])


def ref_to_hash(ref: str):
    return run_cmd(['git', 'rev-parse', f'{ref}^{{}}']).strip()


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
    return match_refs(refs, linear=True)


def match_project(config: Config):
    print('Finding best branch/tag...')
    best_ref, best_score = find_best_branch_tag(config.match_patterns)
    if best_ref is None:
        color_print('Failed to find best ref', color=Color.RED)
        return

    print(f'Found branch/tag: {best_ref}, diff: {best_score}')
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

    matching_refs = list(ref_matching_refs(best_ref))
    if matching_refs:
        print('Matching refs:')
        for ref in matching_refs:
            print(ref)


def skip_project_path(config: Config, project_path: str):
    if config.excluded_project_paths:
        for excluded_project in config.excluded_project_paths:
            if fnmatch.fnmatch(project_path, excluded_project):
                return True

    return False


def skip_project_name(config: Config, project_name: str):
    if config.excluded_projects:
        for excluded_project in config.excluded_projects:
            if fnmatch.fnmatch(project_name, excluded_project):
                return True

        return False

    if config.projects:
        for project in config.projects:
            if fnmatch.fnmatch(project_name, project):
                return False

        return True

    return False


def match_directory(config: Config, tarball_dir_path: str):
    tarball_dir_name = Path(tarball_dir_path).name
    output_tarball_path = Path(config.output_dir, tarball_dir_name)
    shutil.rmtree(output_tarball_path, ignore_errors=True)
    output_tarball_path.mkdir(parents=True)

    aosp_manifest_path = Path(tarball_dir_path, 'aosp_manifest.xml')
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
            project_remote_name = child.attrib.get('remote')
            project_rel_path = child.attrib['path']
            project_name = child.attrib['name']

            if skip_project_name(config, project_name):
                continue

            if skip_project_path(config, project_rel_path):
                continue

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

        project_path = Path(
            config.output_dir, tarball_dir_name, project_rel_path
        )
        project_path.mkdir(parents=True, exist_ok=True)
        project_tarball_path = Path(tarball_dir_path, project_rel_path)

        with WorkingDirectory(str(project_path)):
            init_repo(config, project_name, remote_url)
            copy_tarball_to_repo(project_tarball_path)
            match_project(config)
            print()


def build_match_patterns(
    branch_globs: Optional[List[str]], tag_globs: Optional[List[str]]
):
    match_patterns: List[str] = []

    if branch_globs is None and tag_globs is None:
        branch_globs = ['*']
        tag_globs = ['*']

    if branch_globs is None:
        branch_globs = []

    if tag_globs is None:
        tag_globs = []

    for branch_glob in branch_globs:
        branch_pattern = f'refs/remotes/{REMOTE_NAME}/{branch_glob}'
        match_patterns.append(branch_pattern)

    for tag_glob in tag_globs:
        tag_pattern = f'refs/tags/{tag_glob}'
        match_patterns.append(tag_pattern)

    return match_patterns


def match_manifest_tarball():
    parser = ArgumentParser(
        prog='match_manifest_tarball.py',
        description='Match kernel tarball releases containing'
        'aosp_manifest.xml with public AOSP commits',
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
    parser.add_argument(
        '-o',
        '--output',
        required=True,
        help='Directory in which to output the repositories',
    )
    parser.add_argument(
        '-p',
        '--project',
        action='append',
        default=[],
        help='Glob pattern for matching project names',
    )
    parser.add_argument(
        '-e',
        '--exclude-project',
        action='append',
        default=[],
        help='Glob pattern for not matching project names',
    )
    parser.add_argument(
        '--exclude-project-path',
        action='append',
        default=[],
        help='Glob pattern for not matching project paths',
    )
    parser.add_argument('-m', '--mirror', help='Path to mirror')

    args = parser.parse_args()
    assert not (
        args.project and (args.exclude_project_path or args.exclude_project)
    )
    match_patterns = build_match_patterns(
        args.branch_glob,
        args.tag_glob,
    )
    config = Config(
        match_patterns,
        args.mirror,
        args.output,
        args.project,
        args.exclude_project,
        args.exclude_project_path,
    )

    for dir_path in args.dirs:
        match_directory(config, dir_path)


if __name__ == '__main__':
    match_manifest_tarball()

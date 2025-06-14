#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

import argparse
import sys
from xml.etree import ElementTree


def parse_cmdline() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Add repo to manifest")
    parser.add_argument("--file", help="Path to output manifest.xml")
    parser.add_argument("--project-name", help="Project name")
    parser.add_argument("--project-path", help="Project path")
    parser.add_argument("--project-remote", help="Project remote")
    parser.add_argument("--project-revision", help="Project revision", default=None)
    parser.add_argument("--project-clone-depth", help="Project clone depth", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_cmdline()

    try:
        manifest = ElementTree.parse(args.file)
        manifest = manifest.getroot()
    except:
        manifest = ElementTree.Element("manifest")

    project = ElementTree.Element(
        "project",
        attrib={
            "name": args.project_name,
            "path": args.project_path,
            "remote": args.project_remote,
        },
    )

    if args.project_revision:
        project.attrib["revision"] = args.project_revision

    if args.project_clone_depth:
        project.attrib["clone-depth"] = args.project_clone_depth

    for child in manifest.findall("project"):
        if project.attrib == child.attrib:
            sys.exit("Project with the same attributes already exists")

    manifest.append(project)

    ElementTree.indent(manifest, space="    ")

    with open(args.file, "w") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(ElementTree.tostring(manifest).decode())
        f.write("\n")


if __name__ == "__main__":
    main()

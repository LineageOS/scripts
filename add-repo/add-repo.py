#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

import argparse
import sys
from xml.etree import ElementTree


def parse_cmdline() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Edit / create manifest")

    parser_common = argparse.ArgumentParser(add_help=False)
    parser_common.add_argument(
        "--file", help="Path to output manifest XML", required=True
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparser = subparsers.add_parser("add-project", parents=[parser_common])
    subparser.add_argument("--name", help="Project name", required=True)
    subparser.add_argument("--path", help="Project path", required=True)
    subparser.add_argument("--remote", help="Project remote", required=True)
    subparser.add_argument("--revision", help="Project revision")
    subparser.add_argument("--clone-depth", help="Project clone depth")

    subparser = subparsers.add_parser("add-remote", parents=[parser_common])
    subparser.add_argument("--name", help="Remote name", required=True)
    subparser.add_argument("--fetch", help="Remote path", required=True)

    return parser.parse_args()


# in-place prettyprint formatter
def indent(elem: ElementTree.Element, level: int = 0) -> None:
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            indent(elem, level + 1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


def main() -> None:
    args = parse_cmdline()

    try:
        manifest = ElementTree.parse(args.file)
        manifest = manifest.getroot()
    except:
        manifest = ElementTree.Element("manifest")

    if args.command == "add-project":
        element = ElementTree.Element(
            "project",
            attrib={
                "name": args.name,
                "path": args.path,
                "remote": args.remote,
            },
        )

        if args.revision:
            element.attrib["revision"] = args.revision

        if args.clone_depth:
            element.attrib["clone-depth"] = args.clone_depth
    elif args.command == "add-remote":
        element = ElementTree.Element(
            "remote",
            attrib={
                "name": args.name,
                "fetch": args.fetch,
            },
        )

    for child in manifest.findall(element.tag):
        if element.attrib == child.attrib:
            sys.exit("Element with the same attributes already exists")

    manifest.append(element)

    indent(manifest)

    with open(args.file, "w") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(ElementTree.tostring(manifest).decode())


if __name__ == "__main__":
    main()

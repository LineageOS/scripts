#!/usr/bin/env python

# SPDX-FileCopyrightText: 2023 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

# REUSE-IgnoreStart
import argparse
import os
import re
import sys

from pathlib import Path
from utils import check_dependencies, run_subprocess


def fix_files(project_path, extension, args):
    path_list = Path(project_path).rglob(extension)
    for item in path_list:
        path_in_str = str(item)
        if extension == "*.java" or extension == "*.bp" or extension == "*.proto":
            clean_file(path_in_str, "java", args)
        if extension == "*.bp" or extension == "*.proto":
            clean_file(path_in_str, "bp", args)
        if extension == "*.xml":
            clean_file(path_in_str, "xml", args)
        if extension == "*.py":
            clean_file(path_in_str, "py", args)
    return


def clean_file(file, comment_type, args):
    # We want to ignore translations
    if "/values" in file and not "/values/" in file:
        return_early = True
        can_modify_values = ["land", "large", "night", "television", "v2", "v3"]
        for m in can_modify_values:
            if re.search(rf"/values-{m}", file):
                return_early = False
        if return_early:
            return

    try:
        fh = open(file, "r+")
    except OSError:
        print(f"Something went wrong while opening file {file}")
        return

    content = fh.read()

    copyright_lines = []

    pattern = ""
    if comment_type == "java":
        pattern = r"(/\*.*?\*/)"
    elif comment_type == "xml":
        pattern = r"(<!--.*?-->)"
    elif comment_type == "bp":
        pattern = r"((//[^\n]*\n)*(//)?)"
    elif comment_type == "py":
        pattern = r"((#[^\n]*\n)*#?)"
    match = re.search(pattern, content, re.DOTALL)
    if match is None:
        fh.close()
        return

    comment = match.group(1)
    license_type = get_license_type(comment)
    parts = comment.split("\n")
    if len(parts) == 1:
        fh.close()
        return

    i = 0
    match = None
    while match is None:
        if len(parts) <= i:
            break
        match = re.search(r".*Copyright (?:\([cC]\))?\s*(.*)", parts[i])
        if not match:
            i += 1

    if match is None:
        fh.close()
        return

    copyright_lines.append(match.group(1))
    pattern = re.compile(r"\s*\*?\s+(?:(?:Copyright )?\([Cc]\))?\s*((\d+)(.*))")
    match = pattern.match(parts[i + 1])
    while match is not None:
        copyright_lines.append(match.group(1))
        i += 1
        match = pattern.match(parts[i + 1])

    if license_type is not None:
        new_comment = ""
        if comment_type == "java" or comment_type == "bp":
            new_comment = build_java_spdx_comment(copyright_lines, license_type)
        elif comment_type == "xml":
            new_comment = build_xml_spdx_comment(copyright_lines, license_type)
        elif comment_type == "py":
            new_comment = build_py_spdx_comment(copyright_lines, license_type)
        new_content = content.replace(comment, new_comment)
        if args.fix_newlines:
            if new_content[-1] != "\n":
                new_content += "\n"
        fh.seek(0)
        fh.write(new_content)
        fh.truncate()
    fh.close()


def build_java_spdx_comment(copyright_lines, license_type):
    comment = "/*\n"
    for line in copyright_lines:
        comment += f" * SPDX-FileCopyrightText: {line}\n"
    comment += f" * SPDX-License-Identifier: {license_type}\n */"
    return comment


def build_xml_spdx_comment(copyright_lines, license_type):
    comment = "<!--\n"
    for line in copyright_lines:
        comment += f"     SPDX-FileCopyrightText: {line}\n"
    comment += f"     SPDX-License-Identifier: {license_type}\n-->"
    return comment


def build_py_spdx_comment(copyright_lines, license_type):
    comment = ""
    for line in copyright_lines:
        comment += f"# SPDX-FileCopyrightText: {line}\n"
    comment += f"# SPDX-License-Identifier: {license_type}\n"
    return comment


def get_license_type(comment):
    lic = None
    if "http://www.apache.org/licenses/LICENSE-2.0" in comment:
        lic = "Apache-2.0"
    elif "GNU General Public" in comment and "version 2" in comment:
        lic = "GPL-2.0-or-later"

    return lic


def parse_args():
    parser = argparse.ArgumentParser(description="Make project REUSE compliant")
    parser.add_argument(
        "-r", "--root", default=None, help="Specify the root path of your sources"
    )
    parser.add_argument(
        "-p",
        "--project",
        required=True,
        help="Specify the relative path of the project you want to convert",
    )
    parser.add_argument(
        "-f",
        "--fix_newlines",
        action="store_true",
        help="Add newlines to files that miss them",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    root = args.root
    if args.root is None:
        root = str(Path.cwd())
        root = root.replace("/lineage/scripts/reuse_helper", "")

    path = os.path.join(root, args.project)

    # We need "pipx"
    if not check_dependencies():
        sys.exit(-1)

    # Parse and change known file-/comment-types
    extensions = ["java", "xml", "bp", "proto", "py"]
    for ext in extensions:
        fix_files(path, f"*.{ext}", args)

    # Download all licenses automatically
    os.chdir(path)
    _, code = run_subprocess(["pipx", "run", "reuse", "download", "--all"], True)


if __name__ == "__main__":
    main()
# REUSE-IgnoreEnd

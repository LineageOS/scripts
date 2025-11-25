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
    extension_map = {
        "*.aidl": ["java"],
        "*.flags": ["py"],
        "*.java": ["java"],
        "*.kt": ["java"],
        "*.mk": ["mk"],
        "*.bp": ["go"],
        "*.proto": ["java", "c"],
        "*.xml": ["xml"],
        "*.py": ["py"],
    }
    path_list = Path(project_path).rglob(extension)
    for item in path_list:
        path_in_str = str(item)
        if extension in extension_map:
            for comment_style in extension_map[extension]:
                clean_file(path_in_str, comment_style, args)
    return


def clean_file(file, comment_style, args):
    if should_ignore_file(file):
        return

    try:
        fh = open(file, "r+")
    except OSError:
        print(f"Something went wrong while opening file {file}")
        return

    content = fh.read()

    pattern_map = {
        "c": r"((//[^\n]*\n)*(//)?)",
        "go": r"((//[^\n]*\n)*(//)?)",
        "java": r"(/\*.*?\*/)",
        "mk": r"((#[^\n]*\n)*#?)",
        "py": r"((#[^\n]*\n)*#?)",
        "xml": r"(<!--.*?-->)",
    }
    if comment_style not in pattern_map:
        print(f"Comment style '{comment_style}' unsupported!")
        return
    pattern = pattern_map[comment_style]
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

    copyright_lines = [match.group(1)]
    pattern = re.compile(r"\s*\*?\s+(?:(?:Copyright )?\([Cc]\))?\s*((\d+)(.*))")
    match = pattern.match(parts[i + 1])
    while match is not None:
        copyright_lines.append(match.group(1))
        i += 1
        match = pattern.match(parts[i + 1])

    if license_type is not None:
        new_comment = build_spdx_comment(comment_style, copyright_lines, license_type)
        new_content = content.replace(comment, new_comment)
        if args.fix_newlines:
            if new_content[-1] != "\n":
                new_content += "\n"
        fh.seek(0)
        fh.write(new_content)
        fh.truncate()
    fh.close()


def should_ignore_file(file):
    if not "/res/values-" in file:
       return False
    else:
        # We want to ignore translations
        can_modify_values = ["land", "large", "night", "television", "v2", "v3"]
        for m in can_modify_values:
            if re.search(rf"/values-{m}", file):
                return False
    return True


def build_spdx_comment(comment_style, copyright_lines, license_type):
    if comment_style == "go":
        return build_comment(copyright_lines, license_type, "//\n", "// ", "//\n")
    elif comment_style == "java" or comment_style == "c":
        return build_comment(copyright_lines, license_type, "/*\n", " * ", " */")
    elif comment_style == "mk":
        return build_comment(copyright_lines, license_type, "#\n", "# ", "#\n")
    elif comment_style == "xml":
        return build_comment(copyright_lines, license_type, "<!--\n", "     ", "-->")
    elif comment_style == "py":
        return build_comment(copyright_lines, license_type, "", "# ", "")
    else:
        return ""


def build_comment(copyright_lines, license_type, comment_start, comment_middle, comment_end):
    comment = comment_start
    for line in copyright_lines:
        comment += f"{comment_middle}SPDX-FileCopyrightText: {line}\n"
    comment += f"{comment_middle}SPDX-License-Identifier: {license_type}\n"
    comment += comment_end
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
    extensions = ["aidl", "flags", "java", "kt", "mk", "xml", "bp", "proto", "py"]
    for ext in extensions:
        fix_files(path, f"*.{ext}", args)

    # Download all licenses automatically
    os.chdir(path)
    _, code = run_subprocess(["pipx", "run", "reuse", "download", "--all"], True)


if __name__ == "__main__":
    main()
# REUSE-IgnoreEnd

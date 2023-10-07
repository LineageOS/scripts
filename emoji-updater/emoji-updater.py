#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# SPDX-FileCopyrightText: 2020-2023 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

import os
import requests
import sys

from pathlib import Path

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(
            f"usage: {sys.argv[0]} [url|https://unicode.org/Public/emoji/15.0/emoji-test.txt]"
        )

    url = sys.argv[1]
    req = requests.get(url=url)

    group_name = ""
    items = {}

    for line in req.text.splitlines():
        if line.startswith("# subgroup: "):
            group_name = line.split(maxsplit=2)[-1]
        elif '; fully-qualified' in line and not 'skin tone' in line:
            item = line.split(";")[0].strip().replace(" ", ",")
            items.setdefault(group_name, []).append(item)

    # We want to transfer the received data into the target file
    absolute_path = os.path.dirname(__file__)
    relative_path = "../../../packages/inputmethods/LatinIME/java/res/values-v19/emoji-categories.xml"
    target_path = Path(os.path.join(absolute_path, relative_path)).resolve()

    with open(target_path, "r+") as f:
        lines = f.read()
        f.seek(0)
        f.truncate()

        for key in [*items.keys()]:
            header = f"<!-- {key} -->"
            start = lines.find(header)

            if start != -1:
                while start != -1:
                    end1 = lines.find("</array>", start)
                    end2 = lines.find("<!--", start + 1)

                    if end1 == -1 or end2 == -1:
                        min_end = max(end1, end2)
                    else:
                        min_end = min(end1, end2)
                    replace = lines[start:min_end].rstrip()

                    built = header + "\n"
                    for c in items[key]:
                        built += f"        <item>{c}</item>\n"
                    built = built.rstrip()

                    lines = lines.replace(replace, built)
                    start = lines.find(header, start + len(built))

                del items[key]

        f.write(lines)

    if len(items) > 0:
        print("Could not process the following items automatically:")

        for key in items:
            built = f"        <!-- {key} -->"

            for c in items[key]:
                built += f"\n        <item>{c}</item>"

            print(built)

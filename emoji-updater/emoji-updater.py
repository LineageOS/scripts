#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import requests
import sys

from pathlib import Path

if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(f'usage: {sys.argv[0]} [url|https://unicode.org/Public/emoji/15.0/emoji-test.txt]')

    url = sys.argv[1]
    req = requests.get(url=url)

    output = ''
    group_name = ''
    items = {}
    for line in req.text.splitlines():
        if line.startswith('# subgroup: '):
            group_name = line.split()[-1]
        elif '; fully-qualified' in line:
            item = line.split(";")[0].strip().replace(" ", ",")
            items.setdefault(group_name, []).append(item)

    # We want to transfer the received data into the target file
    absolute_path = os.path.dirname(__file__)
    relative_path = "../../../packages/inputmethods/LatinIME/java/res/values-v19/emoji-categories.xml"
    target_path = Path(os.path.join(absolute_path, relative_path)).resolve()
    with open(target_path, 'r+') as fh:
        lines = fh.read()
        fh.seek(0)
        fh.truncate()

        processed = []
        for key in items:
            header = f'<!-- {key} -->'
            start = lines.find(header)
            if start != -1:
                while start != -1:
                    end1 = lines.find('</array>', start)
                    end2 = lines.find('<!--', start + 1)
                    if end1 == -1 or end2 == -1:
                        min_end = max(end1, end2)
                    else:
                        min_end = min(end1, end2)
                    replace = lines[start:min_end].rstrip()
                    built = header + '\n'
                    for c in items[key]:
                        built += f'        <item>{c}</item>\n'
                    built = built.rstrip()
                    lines = lines.replace(replace, built)
                    start = lines.find(header, start + len(built))
                processed.append(key)
        fh.write(lines)
        fh.flush()
        fh.close()

        for key in processed:
            del items[key]

        if len(items) > 0:
            print('Could not process the following items automatically:')
            for key in items:
                built = f'        <!-- {key} -->'
                for c in items[key]:
                    built += f'\n        <item>{c}</item>'
                print(built)

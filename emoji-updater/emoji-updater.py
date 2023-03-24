#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys

import requests

if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(f'usage: {sys.argv[0]} [url|https://unicode.org/Public/emoji/15.0/emoji-test.txt]')

    url = sys.argv[1]
    req = requests.get(url=url)

    for line in req.text.splitlines():
        if line.startswith('# subgroup: '):
            print(f'        <!-- {line.split(maxsplit=2)[-1]} -->')
        elif '; fully-qualified' in line and not 'skin tone' in line:
            print(f'        <item>{line.split(";")[0].strip().replace(" ", ",")}</item>')

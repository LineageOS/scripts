#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys

import requests
from lxml import etree


def get_emoji_variants():
    url = 'https://unicode.org/emoji/charts/emoji-variants.html'
    req = requests.get(url=url)

    parser = etree.HTMLParser(recover=True, encoding='utf-8')
    doc = etree.fromstring(text=req.content, parser=parser)

    return [ x.attrib['name'] for x in doc.xpath('.//td[@class="code cchars"]/a') ]


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(f'usage: {sys.argv[0]} [url|https://unicode.org/emoji/charts-12.0/full-emoji-list.html]')

    url = sys.argv[1]
    req = requests.get(url=url)

    parser = etree.HTMLParser(recover=True, encoding='utf-8')
    doc = etree.fromstring(text=req.content, parser=parser)

    emoji_variants = get_emoji_variants()

    for tr in doc.xpath('.//tr'):
        mediumhead = tr.xpath('.//th[@class="mediumhead"]/a')

        if len(mediumhead) > 0:
            print(f'        <!-- {mediumhead[0].text} -->')
            continue

        code = tr.xpath('.//td[@class="code"]/a')

        if len(code) > 0:
            codes = ','.join([x[2:] for x in code[0].text.split()])

            # Add Variation Selector-16 to emojis that have default text presentation
            if codes in emoji_variants:
                codes += ",FE0F"

            print(f'        <item>{codes}</item>')
            continue

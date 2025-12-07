#!/usr/bin/env python3
#
# Tries to get device-specific info from various Google sites
# Best effort
# We require manual input of build id here to keep things easier

import argparse
import base64
from functools import partial
import re
from bs4 import BeautifulSoup
from git import cmd
import os
import urllib.request

SCRIPT_PATH = os.path.realpath(os.path.dirname(__file__))
VARS_PATH = SCRIPT_PATH + os.path.sep + os.path.pardir + os.path.sep + "vars"

IMAGE_URL = "https://developers.google.com/android/images"
OTA_URL = "https://developers.google.com/android/ota"
COOKIE = {'Cookie': 'devsite_wall_acks=nexus-image-tos,nexus-ota-tos'}

def handle_image(soup, html_id, output_fn):
    td = soup.find(id=html_id).find_all('td')
    flash_url = td[1].a['href']
    image_url = td[2].a['href']
    image_sha256 = td[3].contents[0]
    build_number = flash_url.split("/")[4].split("?")[0]
    output_fn('new_build_number="{0}"\nnew_flash_url="{1}"\nnew_image_url="{2}"\nnew_image_sha256="{3}"'.format(build_number, flash_url, image_url, image_sha256))

def handle_ota(soup, html_id, output_fn):
    td = soup.find(id=html_id).find_all('td')
    ota_url = td[1].a['href']
    ota_sha256 = td[2].contents[0]
    output_fn('new_ota_url="{0}"\nnew_ota_sha256="{1}"'.format(ota_url, ota_sha256))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--devices', help="Device codenames", type=str, nargs='+', required=True)
    parser.add_argument('--build-ids', help="Build IDs", type=str, nargs='+', required=True)
    parser.add_argument('--tmps', help="Temporary files to store device vars into", type=str, nargs='+', required=True)
    args = parser.parse_args()

    assert len(args.devices) == len(args.build_ids) == len(args.tmps)

    image_html = urllib.request.urlopen(urllib.request.Request(IMAGE_URL, headers=COOKIE)).read()
    image_soup = BeautifulSoup(image_html, 'html.parser')

    ota_html = urllib.request.urlopen(urllib.request.Request(OTA_URL, headers=COOKIE)).read()
    ota_soup = BeautifulSoup(ota_html, 'html.parser')

    def handle_device(device, build_id, output_fn):
        html_id = "{0}{1}".format(device, build_id.lower())
        handle_image(image_soup, html_id, output_fn)
        handle_ota(ota_soup, html_id, output_fn)

    for device, build_id, tmp in zip(args.devices, args.build_ids, args.tmps):
        with open(tmp, 'w', encoding='utf-8') as f:
            def output_fns(fs, s):
                fs.write(s)
                fs.write('\n')

            output_fn = partial(output_fns, f)
            handle_device(device, build_id, output_fn)


if __name__ == "__main__":
    main()

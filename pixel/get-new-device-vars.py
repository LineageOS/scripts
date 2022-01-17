#!/usr/bin/env python3
#
# Tries to get device-specific info from various Google sites
# Best effort
# We require manual input of build id here to keep things easier

import argparse
import base64
from bs4 import BeautifulSoup
from git import cmd
import os
import urllib.request

SCRIPT_PATH = os.path.realpath(os.path.dirname(__file__))
VARS_PATH = SCRIPT_PATH + os.path.sep + os.path.pardir + os.path.sep + "vars"

IMAGE_URL = "https://developers.google.com/android/images"
OTA_URL = "https://developers.google.com/android/ota"
COOKIE = {'Cookie': 'devsite_wall_acks=nexus-image-tos,nexus-ota-tos'}

PLATFORM_BUILD_URL = "https://android.googlesource.com/platform/build"
BUILD_ID_URL = "https://android.googlesource.com/platform/build/+/refs/tags/{}/core/build_id.mk?format=TEXT"
BUILD_ID_FILTER = "BUILD_ID="
SECURITY_PATCH_URL = "https://android.googlesource.com/platform/build/+/refs/tags/{}/core/version_defaults.mk?format=TEXT"
SECURITY_PATCH_FILTER = "PLATFORM_SECURITY_PATCH :="

def handle_image(html_id):
    image_html = urllib.request.urlopen(urllib.request.Request(IMAGE_URL, headers=COOKIE)).read()
    soup = BeautifulSoup(image_html, 'html.parser')
    td = soup.find(id=html_id).find_all('td')
    flash_url = td[1].a['href']
    image_url = td[2].a['href']
    image_sha256 = td[3].contents[0]
    build_number = flash_url.split("/")[4].split("?")[0]
    print('new_build_number="{0}"\nnew_flash_url="{1}"\nnew_image_url="{2}"\nnew_image_sha256="{3}"'.format(build_number, flash_url, image_url, image_sha256))

def handle_ota(html_id):
    ota_html = urllib.request.urlopen(urllib.request.Request(OTA_URL, headers=COOKIE)).read()
    soup = BeautifulSoup(ota_html, 'html.parser')
    td = soup.find(id=html_id).find_all('td')
    ota_url = td[1].a['href']
    ota_sha256 = td[2].contents[0]
    print('new_ota_url="{0}"\nnew_ota_sha256="{1}"'.format(ota_url, ota_sha256))

def get_all_aosp_tags(tag_filter):
    all_tags = []
    for line in cmd.Git().ls_remote("--sort=v:refname", PLATFORM_BUILD_URL, tag_filter, tags=True, refs=True).split('\n'):
        try:
            (ref, tag) = line.split('\t')
        except ValueError:
            pass
        all_tags.append(tag.replace("refs/tags/", ""))
    return all_tags

def get_aosp_tag_for_build_id(aosp_tags, wanted_build_id):
    for aosp_tag in aosp_tags:
        output = base64.decodebytes(urllib.request.urlopen(BUILD_ID_URL.format(aosp_tag)).read()).decode()
        for line in output.split('\n'):
            if BUILD_ID_FILTER in line:
                found_build_id = line.split("=")[1]
                if found_build_id == wanted_build_id:
                    print('new_aosp_tag="{0}"'.format(aosp_tag))
                    return aosp_tag

def get_security_patch_for_aosp_tag(aosp_tag):
    output = base64.decodebytes(urllib.request.urlopen(SECURITY_PATCH_URL.format(aosp_tag)).read()).decode()
    for line in output.split('\n'):
        if SECURITY_PATCH_FILTER in line:
            security_patch = line.split(":=")[1].strip()
            print('new_security_patch="{0}"'.format(security_patch))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-b', '--build_id', help="Build ID", type=str, required=True)
    parser.add_argument('-d', '--device', help="Device codename", type=str, required=True)
    parser.add_argument('-v', '--version', default="12.0", help='Android version', type=str)
    args = parser.parse_args()
    html_id = "{0}{1}".format(args.device, args.build_id.lower())
    handle_image(html_id)
    handle_ota(html_id)
    aosp_tag = get_aosp_tag_for_build_id(get_all_aosp_tags("android-{0}*".format(args.version)), args.build_id.upper())
    get_security_patch_for_aosp_tag(aosp_tag)

if __name__ == "__main__":
    main()

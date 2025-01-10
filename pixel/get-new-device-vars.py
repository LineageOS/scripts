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

PLATFORM_BUILD_URL = "https://android.googlesource.com/platform/build"
BUILD_ID_URL = "https://android.googlesource.com/platform/build/+/refs/{}/core/build_id.mk?format=TEXT"
BUILD_ID_FILTER = "BUILD_ID="
SECURITY_PATCH_URL = "https://android.googlesource.com/platform/build/+/refs/{}/core/version_defaults.mk?format=TEXT"
SECURITY_PATCH_FILTER = "PLATFORM_SECURITY_PATCH :="
NEW_SECURITY_PATCH_URL = "https://android.googlesource.com/platform/build/release/+/refs/tags/{}/flag_values/{}/RELEASE_PLATFORM_SECURITY_PATCH.textproto?format=TEXT"
NEW_SECURITY_PATCH_FILTER = "string_value: "

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

def get_all_aosp_tags(tag_filter):
    all_tags = []
    try:
        for line in cmd.Git().ls_remote("--sort=v:refname", PLATFORM_BUILD_URL, tag_filter, tags=True, refs=True).split('\n'):
            try:
                (ref, tag) = line.split('\t')
            except ValueError:
                pass
            all_tags.append(tag.replace("refs/tags/", ""))
        return all_tags
    except Exception as e:
        return all_tags

def get_aosp_tags_for_build_ids(aosp_tags, m):
    try:
        for aosp_tag in aosp_tags:
            output = base64.decodebytes(urllib.request.urlopen(BUILD_ID_URL.format("tags/" + aosp_tag)).read()).decode()
            for line in output.split('\n'):
                if BUILD_ID_FILTER in line:
                    found_build_id = line.split("=")[1]
                    m[found_build_id] = aosp_tag
    except Exception as e:
        pass

def get_security_patch_for_aosp_tag(aosp_tag):
    try:
        output = base64.decodebytes(urllib.request.urlopen(SECURITY_PATCH_URL.format("tags/" + aosp_tag)).read()).decode()
    except:
        return None

    for line in output.split('\n'):
        if SECURITY_PATCH_FILTER in line:
            security_patch = line.split(":=")[1].strip()
            return security_patch

    return None

def get_security_patches_for_aosp_tags(aosp_tags, m):
    for aosp_tag in aosp_tags:
        security_patch = get_security_patch_for_aosp_tag(aosp_tag)
        if security_patch is None:
            continue

        m[aosp_tag] = security_patch


def get_security_patch(aosp_tag, release):
    try:
        url = NEW_SECURITY_PATCH_URL.format(aosp_tag, release)
        output = base64.decodebytes(urllib.request.urlopen(url).read()).decode()
    except:
        return None

    for line in output.split('\n'):
        if NEW_SECURITY_PATCH_FILTER in line:
            match = re.search(r'\d{4}-\d{2}-\d{2}', line)
            security_patch = match.group(0) if match else None
            return security_patch

    return None


def get_security_patches(aosp_tags, build_ids, m):
    for build_id in build_ids:
        release, _ = build_id.split('.', 1)
        release = release.lower()

        for aosp_tag in aosp_tags:
            security_patch = get_security_patch(aosp_tag, release)
            if security_patch is None:
                continue

            m[aosp_tag] = security_patch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--devices', help="Device codenames", type=str, nargs='+', required=True)
    parser.add_argument('--build-ids', help="Build IDs", type=str, nargs='+', required=True)
    parser.add_argument('--tmps', help="Temporary files to store device vars into", type=str, nargs='+', required=True)
    parser.add_argument('-t', '--tags_match', default="android-13.0", help='Android version tag to match', type=str)
    args = parser.parse_args()

    assert len(args.devices) == len(args.build_ids) == len(args.tmps)

    image_html = urllib.request.urlopen(urllib.request.Request(IMAGE_URL, headers=COOKIE)).read()
    image_soup = BeautifulSoup(image_html, 'html.parser')

    ota_html = urllib.request.urlopen(urllib.request.Request(OTA_URL, headers=COOKIE)).read()
    ota_soup = BeautifulSoup(ota_html, 'html.parser')

    all_aosp_tags = get_all_aosp_tags("{0}*".format(args.tags_match))
    build_ids = set(args.build_ids)

    build_id_aosp_tag_map = {}
    get_aosp_tags_for_build_ids(all_aosp_tags, build_id_aosp_tag_map)

    aosp_tag_security_patch_map = {}
    get_security_patches_for_aosp_tags(all_aosp_tags, aosp_tag_security_patch_map)
    get_security_patches(all_aosp_tags, build_ids, aosp_tag_security_patch_map)

    def handle_device(device, build_id, output_fn):
        html_id = "{0}{1}".format(device, build_id.lower())
        handle_image(image_soup, html_id, output_fn)
        handle_ota(ota_soup, html_id, output_fn)
        aosp_tag = build_id_aosp_tag_map.get(build_id, 'unknown')
        output_fn('new_aosp_tag="{0}"'.format(aosp_tag))
        security_patch = aosp_tag_security_patch_map.get(aosp_tag, 'unknown')
        output_fn('new_security_patch="{0}"'.format(security_patch))

    for device, build_id, tmp in zip(args.devices, args.build_ids, args.tmps):
        with open(tmp, 'w', encoding='utf-8') as f:
            def output_fns(fs, s):
                fs.write(s)
                fs.write('\n')

            output_fn = partial(output_fns, f)
            handle_device(device, build_id, output_fn)


if __name__ == "__main__":
    main()

#!/usr/bin/env python
# -*- coding: utf-8 -*-

# SPDX-FileCopyrightText: 2019-2026 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import print_function

import argparse
import parse
import struct


def parse_cmdline():
    parser = argparse.ArgumentParser(
        description='Convert /vendor/etc/group × /(system|vendor)/etc/(fs_config_dirs|fs_config_files) to config.fs')
    parser.add_argument('capability_header_path',
                        help='path to {android}/bionic/libc/kernel/uapi/linux/capability.h')
    parser.add_argument('android_filesystem_config_header_path',
                        help='path to {android}/system/core/libcutils/include/private/android_filesystem_config.h')
    parser.add_argument('vendor_group_path',
                        help='path to {rom}/vendor/etc/group')
    parser.add_argument('fs_config_paths', nargs='+',
                        help='paths to {rom}/(system|vendor)/etc/fs_config_(dirs|files)')
    return parser.parse_args()


def get_capabilities(capability_header_path):
    capabilities = {}

    with open(capability_header_path, 'r') as file:
        for line in file:
            s = parse.search('#define CAP_{:w} {:d}', line)

            if s is not None:
                capabilities[s[1]] = s[0]

    return capabilities


def get_groups(android_filesystem_config_header_path, vendor_group_path):
    system_groups = {}
    vendor_groups = {}

    with open(android_filesystem_config_header_path, 'r') as file:
        for line in file:
            s = parse.search('#define AID_{:w} {:d}', line)

            if s is not None:
                system_groups[s[1]] = 'AID_' + s[0]

    with open(vendor_group_path, 'r') as file:
        for line in file:
            name, _, uid, _ = line.split(':', 3)
            vendor_groups[int(uid)] = 'AID_' + name.upper()

    return system_groups, vendor_groups


def get_fs_path_configs(fs_config_paths, system_groups, vendor_groups):
    fs_path_config = {}

    for fs_config_path in args.fs_config_paths:
        with open(fs_config_path, 'rb') as file:
            while True:
                bytes = file.read(struct.calcsize('<HHHHQ'))

                if bytes == b'':
                    break

                length, mode, uid, gid, caps = struct.unpack('<HHHHQ', bytes)
                name = file.read(length - len(bytes)).decode().rstrip('\x00')

                fs_path_config[name] = {
                    'mode': mode,
                    'user': gid_to_str(uid, system_groups, vendor_groups),
                    'group': gid_to_str(gid, system_groups, vendor_groups),
                    'caps': caps_to_str(caps)
                }

    return fs_path_config


def caps_to_str(caps):
    caps_list = []

    # return '0' directly if there are no special capabilities set
    if caps == 0:
        return str(caps)

    # try to match well known linux capabilities
    for cap in capabilities:
        cap_mask_long = 1 << cap

        if caps & cap_mask_long:
            caps = caps & ~cap_mask_long
            caps_list.append(capabilities[cap])

    # append unmatched caps if needed
    if caps > 0:
        caps_list.append(str(caps))

    return ' '.join(caps_list)


def gid_to_str(gid, system_groups, vendor_groups):
    if gid in system_groups:
        return system_groups[gid]

    if gid in vendor_groups:
        return vendor_groups[gid]

    return gid


if __name__ == '__main__':
    args = parse_cmdline()
    capabilities = get_capabilities(args.capability_header_path)
    system_groups, vendor_groups = get_groups(
        args.android_filesystem_config_header_path,
        args.vendor_group_path)
    fs_path_configs = get_fs_path_configs(
        args.fs_config_paths,
        system_groups,
        vendor_groups)

    # print vendor AIDs
    for gid in sorted(vendor_groups):
        print('[{}]'.format(vendor_groups[gid]))
        print('value:{}'.format(gid))
        print()

    # print {system,vendor} fs path configs
    for name in sorted(fs_path_configs):
        print('[{}]'.format(name))
        print('mode: {:04o}'.format(fs_path_configs[name]['mode']))
        print('user: {}'.format(fs_path_configs[name]['user']))
        print('group: {}'.format(fs_path_configs[name]['group']))
        print('caps: {}'.format(fs_path_configs[name]['caps']))
        print()

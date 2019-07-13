#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

import argparse
import parse
import struct


def parse_cmdline():
    parser = argparse.ArgumentParser(
        description='Convert /vendor/etc/group × /(system|vendor)/etc/(fs_config_dirs|fs_config_files) to config.fs')
    parser.add_argument('capability_header_path',
                        help='path to {kernel}/include/uapi/linux/capability.h')
    parser.add_argument('system_filesystem_config_path',
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
            s = parse.search('#define CAP_{} {:d}', line)

            if s is not None and len(s[0].split()) == 1:
                capabilities[s[1]] = s[0].strip()

    return capabilities


def get_groups(system_filesystem_config_path, vendor_group_path):
    system_groups = {}
    vendor_groups = {}

    with open(system_filesystem_config_path, 'r') as file:
        for line in file:
            if not line.startswith('#define AID_'):
                continue

            s = parse.search('#define {} {:d}', line)

            if s is not None:
                system_groups[s[1]] = s[0]

    with open(vendor_group_path, 'r') as file:
        for line in file:
            name, _, uid, _ = line.strip().split(":", 3)
            vendor_groups[uid] = "AID_" + name.upper()

    return system_groups, vendor_groups


def get_fs_path_configs(fs_config_paths, system_groups, vendor_groups):
    fs_path_config = {}

    for fs_config_path in args.fs_config_paths:
        with open(fs_config_path, 'rb') as file:
            while True:
                bytes = file.read(struct.calcsize('<HHHHQ'))

                if bytes is b'':
                    break

                length, mode, uid, gid, caps = struct.unpack('<HHHHQ', bytes)
                name = file.read(length - len(bytes)).rstrip('\x00').decode()

                fs_path_config[name] = {
                    "mode": mode,
                    "user": gid_to_str(uid, system_groups, vendor_groups),
                    "group": gid_to_str(gid, system_groups, vendor_groups),
                    "caps": caps_to_str(caps)
                }

    return fs_path_config


def caps_to_str(caps):
    caps_str = ''

    for i in capabilities:
        if caps & (1 << i):
            caps = caps & ~(1 << i)
            caps_str += capabilities[i] + ' '

    if caps != 0 or len(caps_str) == 0:
        caps_str += str(caps) + ' '

    return caps_str.strip()


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
        args.system_filesystem_config_path,
        args.vendor_group_path)
    fs_path_configs = get_fs_path_configs(
        args.fs_config_paths,
        system_groups,
        vendor_groups)

    for gid in sorted(vendor_groups):
        print('[{}]'.format(vendor_groups[gid]))
        print('value:{}'.format(gid))
        print()

    for name in sorted(fs_path_configs):
        print('[{}]'.format(name))
        print('mode: {:04o}'.format(fs_path_configs[name]["mode"]))
        print('user: {}'.format(fs_path_configs[name]["user"]))
        print('group: {}'.format(fs_path_configs[name]["group"]))
        print('caps: {}'.format(fs_path_configs[name]["caps"]))
        print()

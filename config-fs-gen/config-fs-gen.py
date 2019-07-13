#!/usr/bin/env python

from __future__ import print_function

import argparse
import parse
import struct


def parse_cmdline():
    parser = argparse.ArgumentParser(
        description='Convert /vendor/etc/(fs_config_files|group) to config.fs')
    parser.add_argument('capability_header_path',
                        help='path to {kernel}/include/uapi/linux/capability.h')
    parser.add_argument('system_filesystem_config_path',
                        help='path to {android}/system/core/libcutils/include/private/android_filesystem_config.h')
    parser.add_argument('vendor_group_path',
                        help='path to {rom}/vendor/etc/group')
    parser.add_argument('vendor_fs_config_files_path',
                        help='path to {rom}/vendor/etc/fs_config_files')
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

    for gid in sorted(vendor_groups):
        print('[{}]'.format(vendor_groups[gid]))
        print('value:{}'.format(gid))
        print()

    with open(args.vendor_fs_config_files_path, 'rb') as file:
        while True:
            bytes = file.read(struct.calcsize('<HHHHQ'))

            if bytes is b'':
                break

            length, mode, uid, gid, caps = struct.unpack('<HHHHQ', bytes)
            name = file.read(length - len(bytes)).rstrip('\x00').decode()

            print('[{}]'.format(name))
            print('mode: {:04o}'.format(mode))
            print('user: {}'.format(
                gid_to_str(uid, system_groups, vendor_groups)))
            print('group: {}'.format(
                gid_to_str(gid, system_groups, vendor_groups)))
            print('caps: {}'.format(caps_to_str(caps)))
            print()

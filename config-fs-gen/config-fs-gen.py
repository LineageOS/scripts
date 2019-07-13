#!/usr/bin/env python

from __future__ import print_function

import argparse, parse, struct

parser = argparse.ArgumentParser(description='Convert /vendor/etc/(fs_config_files|group) to config.fs')
parser.add_argument('capability_header_path',
                    help='path to {kernel}/include/uapi/linux/capability.h')
parser.add_argument('system_filesystem_config_path',
                    help='path to {android}/system/core/libcutils/include/private/android_filesystem_config.h')
parser.add_argument('vendor_group_path',
                    help='path to {rom}/vendor/etc/group')
parser.add_argument('vendor_fs_config_files_path',
                    help='path to {rom}/vendor/etc/fs_config_files')

args = parser.parse_args()

capabilities = {}

with open(args.capability_header_path, 'r') as file:
    for line in file:
       s = parse.search('#define CAP_{} {:d}', line)

       if s != None and len(s[0].split()) == 1:
          capabilities[s[1]] = s[0].strip()

groups = {}

with open(args.system_filesystem_config_path, 'r') as file:
    for line in file:
       if not line.startswith('#define AID_'):
           continue

       s = parse.search('#define {} {:d}', line)

       if s != None:
           groups[s[1]] = s[0]

with open(args.vendor_group_path, 'r') as file:
    for line in file:
        name, _, uid, _ = line.strip().split(":", 3)
        groups[uid] = "AID_" + name.upper()

        print('[{}]'.format(groups[uid]))
        print('value:{}'.format(uid))
        print('')

with open(args.vendor_fs_config_files_path, 'rb') as file:
    while True:
        length = file.read(2)

        if length is b'':
            break

        length = struct.unpack('<H', length)[0]
        mode = struct.unpack('<H', file.read(2))[0]
        uid = struct.unpack('<H', file.read(2))[0]
        gid = struct.unpack('<H', file.read(2))[0]
        caps = struct.unpack('<Q', file.read(8))[0]
        name = file.read(length - 16).decode()

        caps_str = ''

        for i in capabilities:
            if caps & (1 << i):
                caps = caps & ~(1 << i)
                caps_str += capabilities[i] + ' '

        if caps != 0 or len(caps_str) == 0:
             caps_str += str(caps) + ' '

        print('[{}]'.format(name))
        print('mode: 0{:o}'.format(mode))
        print('user: {}'.format(groups[uid] if uid in groups else uid))
        print('group: {}'.format(groups[gid] if gid in groups else gid))
        print('caps: {}'.format(caps_str.strip()))
        print('')

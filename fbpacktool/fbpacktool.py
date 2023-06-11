#!/usr/bin/env python3
#
# Copyright 2021 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import argparse
import logging
import os
import sys
from lxml.etree import XMLParser
import yaml

#from google3.third_party.devsite.androidsource.en.docs.core.architecture.bootloader.tools.pixel.fw_unpack import fbpack
import fbpack

def bytes_to_str(bstr):
  return bstr.decode().rstrip('\x00')


def print_pack_header(pack):
  print('magic:              {:#x}'.format(pack.magic))
  print('version:            {}'.format(pack.version))
  print('header size:        {}'.format(pack.header_size))
  print('entry header size:  {}'.format(pack.entry_header_size))
  platform = bytes_to_str(pack.platform)
  print('platform:           {}'.format(platform))
  pack_version = bytes_to_str(pack.pack_version)
  print('pack version:       {}'.format(pack_version))
  print('slock type:         {}'.format(pack.slot_type))
  print('data align:         {}'.format(pack.data_align))
  print('total entries:      {}'.format(pack.total_entries))
  print('total size:         {}'.format(pack.total_size))


def print_pack_entry(entry, prefix):
  name = bytes_to_str(entry.name)
  print('{}name:       {}'.format(prefix, name))
  etype = 'unknown'
  if entry.type == fbpack.FBPACK_PARTITION_TABLE:
    etype = 'partiton table'
  elif entry.type == fbpack.FBPACK_PARTITION_DATA:
    etype = 'partition'
  elif entry.type == fbpack.FBPACK_SIDELOAD_DATA:
    etype = 'sideload'
  else:
    print('entry else')
  print('{}type:       {}'.format(prefix, etype))
  product = bytes_to_str(entry.product)
  print('{}product:    {}'.format(prefix, product))
  print('{}offset:     {:#x} ({})'.format(prefix, entry.offset, entry.offset))
  print('{}size:       {:#x} ({})'.format(prefix, entry.size, entry.size))
  print('{}slotted:    {}'.format(entry.size, bool(entry.slotted)))
  print('{}crc32:      {:#08x}'.format(prefix, entry.crc32))


def cmd_info(args):
  with open(args.file, 'rb') as f:
    pack = fbpack.PackHeader.from_bytes(f.read(len(fbpack.PackHeader())))

    if pack.version != fbpack.FBPACK_VERSION:
      raise NotImplementedError('unsupported version {}'.format(pack.version))

    print('Header:')
    print_pack_header(pack)

    print('\nEntries:')
    for i in range(1, pack.total_entries + 1):
      entry = fbpack.PackEntry.from_bytes(f.read(len(fbpack.PackEntry())))
      print('Entry {}: {{'.format(i))
      print_pack_entry(entry, '    ')
      print('}')


def align_up(val, align):
  return (val + align - 1) & ~(align - 1)


def create_pack_file(file_name, in_dir_name, pack):
  pack.total_entries = len(pack.entries)
  offset = pack.header_size + pack.total_entries * pack.entry_header_size
  with open(file_name, 'wb') as f:
    # write entries data
    for entry in pack.entries:
      # align data
      offset = align_up(offset, pack.data_align)
      entry.offset = offset
      f.seek(offset)
      fin_name = os.path.join(in_dir_name, entry.filepath)
      with open(fin_name, 'rb') as fin:
        data = fin.read()
        entry.size = len(data)
        f.write(data)
        offset += len(data)

    pack.total_size = offset
    f.seek(0)
    # write pack header
    f.write(bytes(pack))
    # iterate over entries again to write entry header
    for entry in pack.entries:
      f.write(bytes(entry))


def cmd_create(args):
  if not (args.file.lower().endswith('.xml') or
          args.file.lower().endswith('.yaml')):
    raise NotImplementedError('{} type not supported'.format(args.file))

  pack = None
  if args.file.lower().endswith('.yaml'):
    pack = yaml.parse(args.file)
  else:
    pack = XMLParser.parse(args.file)
  pack.pack_version = bytes(str(args.pack_version).encode('ascii'))
  pack.header_size = len(pack)

  # create output directory if missing
  if not os.path.isdir(args.out_dir):
    os.makedirs(args.out_dir, 0o755)

  file_name = os.path.join(args.out_dir, pack.name + '.img')

  create_pack_file(file_name, args.in_dir, pack)


def product_match(products, product):
  return product in products.split(b'|')


def copyfileobj(src, dst, file_size):
  while file_size > 0:
    buf = src.read(min(128 * 1024, file_size))
    dst.write(buf)
    file_size -= len(buf)


def cmd_unpack(args):
  with open(args.file, 'rb') as f:
    pack = fbpack.PackHeader.from_bytes(f.read(len(fbpack.PackHeader())))

    if pack.version != fbpack.FBPACK_VERSION:
      raise NotImplementedError('unsupported version {}'.format(pack.version))

    entries = []
    # create list of entries we want to extact
    for _ in range(pack.total_entries):
      entry = fbpack.PackEntry.from_bytes(f.read(len(fbpack.PackEntry())))
      name = bytes_to_str(entry.name)
      if not args.partitions or name in args.partitions:
        # if both product are valid then match product name too
        if not args.product or not entry.product or product_match(
            entry.product, args.product):
          entries.append(entry)

    if not entries and not args.unpack_ver:
      raise RuntimeError('no images to unpack')

    # create output directory if it does not exist
    if not os.path.isdir(args.out_dir):
      os.makedirs(args.out_dir, 0o755)

    out_files = {}
    # write file per entry
    for entry in entries:
      name = bytes_to_str(entry.name)
      logging.info('Unpacking {} (size: {}, offset: {})'.format(
          name, entry.size, entry.offset))
      f.seek(entry.offset)
      entry_filename = os.path.join(args.out_dir, name + '.img')
      instance = out_files.get(entry_filename, 0) + 1
      out_files[entry_filename] = instance
      if instance > 1:
        entry_filename = os.path.join(args.out_dir,
                                      name + '({}).img'.format(instance - 1))
      with open(entry_filename, 'wb') as entry_file:
        copyfileobj(f, entry_file, entry.size)

    if args.unpack_ver:
      ver_file_path = os.path.join(args.out_dir, 'version.txt')
      with open(ver_file_path, 'w') as ver_file:
        ver_file.write(bytes_to_str(pack.pack_version))

  logging.info('Done')


def parse_args():
  parser = argparse.ArgumentParser(
      description='Tool to create/modify/inspect fastboot packed images')
  parser.add_argument(
      '-v',
      '--verbosity',
      action='count',
      default=0,
      help='increase output verbosity')

  subparsers = parser.add_subparsers()

  # info command
  info = subparsers.add_parser('info')
  info.add_argument('file', help='packed image file')
  info.set_defaults(func=cmd_info)

  # create command
  create = subparsers.add_parser('create')
  create.add_argument(
      '-d', '--in_dir', help='directory to search for data files', default='.')
  create.add_argument(
      '-o',
      '--out_dir',
      help='output directory for the packed image',
      default='.')
  create.add_argument(
      '-v', '--pack_version', help='Packed image version ', default='')
  create.add_argument(
      'file', help='config file describing packed image (yaml/xml)')
  create.set_defaults(func=cmd_create)

  # unpack command
  unpack = subparsers.add_parser('unpack')
  unpack.add_argument(
      '-o', '--out_dir', help='directory to store unpacked images', default='.')
  unpack.add_argument(
      '-p', '--product', help='filter images by product', default='')
  unpack.add_argument(
      '-v',
      '--unpack_ver',
      help='Unpack version to a file',
      action='store_true')
  unpack.add_argument('file', help='packed image file')
  unpack.add_argument(
      'partitions',
      metavar='PART',
      type=str,
      nargs='*',
      help='Partition names to extract (default all).')
  unpack.set_defaults(func=cmd_unpack)

  args = parser.parse_args()
  # make sure a command was passed
  if not hasattr(args, 'func'):
    parser.print_usage()
    print('fbpacktool.py: error: no command was passed')
    sys.exit(2)

  return args


def main():
  args = parse_args()

  if args.verbosity >= 2:
    log_level = logging.DEBUG
  elif args.verbosity == 1:
    log_level = logging.INFO
  else:
    log_level = logging.WARNING

  logging.basicConfig(level=log_level)

  # execute command
  args.func(args)


if __name__ == '__main__':
  main()

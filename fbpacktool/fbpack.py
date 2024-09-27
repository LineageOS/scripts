# SPDX-FileCopyrightText: 2021 The Android Open Source Project
# SPDX-License-Identifier: Apache-2.0
import collections

#from google3.third_party.devsite.androidsource.en.docs.core.architecture.bootloader.tools.pixel.fw_unpack import packedstruct
import packedstruct

FBPACK_MAGIC = 0x4b504246   # "FBPK"  FastBook PacK
FBPACK_VERSION = 2
FBPACK_VERSION_V1 = 1
FBPACK_DEFAULT_DATA_ALIGN = 16

FBPACK_PARTITION_TABLE = 0
FBPACK_PARTITION_DATA = 1
FBPACK_SIDELOAD_DATA = 2


class CommonPackHeader(packedstruct.PackedStruct):
  magic: int
  version: int
  _FIELDS = collections.OrderedDict([
      ('magic', 'I'),
      ('version', 'I'),
  ])

  def __init__(self,
               magic=FBPACK_MAGIC,
               version=FBPACK_VERSION_V1):
    super().__init__(magic, version)


class PackEntry(packedstruct.PackedStruct):
  """Pack entry info."""

  type: int
  name: bytes
  product: bytes
  offset: int
  size: int
  slotted: int
  crc32: int
  _FIELDS = collections.OrderedDict([
      ('type', 'I'),
      ('name', '36s'),
      ('product', '40s'),
      ('offset', 'Q'),
      ('size', 'Q'),
      ('slotted', 'I'),
      ('crc32', 'I'),
  ])

  # Provide defaults.
  # pylint: disable=useless-super-delegation
  def __init__(self,
               type_=0,
               name=b'',
               prod=b'',
               offset=0,
               size=0,
               slotted=0,
               crc32=0):
    super(PackEntry, self).__init__(type_, name, prod, offset, size, slotted,
                                    crc32)


class PackHeader(packedstruct.PackedStruct):
  """ A packed image representation"""

  magic: int
  version: int
  header_size: int
  entry_header_size: int
  platform: bytes
  pack_version: bytes
  slot_type: int
  data_align: int
  total_entries: int
  total_size: int
  _FIELDS = collections.OrderedDict([
      ('magic', 'I'),
      ('version', 'I'),
      ('header_size', 'I'),
      ('entry_header_size', 'I'),
      ('platform', '16s'),
      ('pack_version', '64s'),
      ('slot_type', 'I'),
      ('data_align', 'I'),
      ('total_entries', 'I'),
      ('total_size', 'I'),
  ])

  def __init__(self,
               magic=FBPACK_MAGIC,
               version=FBPACK_VERSION,
               header_size=0,
               entry_header_size=len(PackEntry()),
               platform=b'',
               pack_version=b'',
               slot_type=0,
               data_align=FBPACK_DEFAULT_DATA_ALIGN,
               total_entries=0,
               total_size=0):
    super(PackHeader,
          self).__init__(magic, version, header_size, entry_header_size,
                         platform, pack_version, slot_type, data_align,
                         total_entries, total_size)
    # update header size once we know all fields
    self.header_size = len(self)


class PackHeaderV1(packedstruct.PackedStruct):
  magic: int
  version: int
  img_version: str
  total_entries: int
  total_size: int
  _FIELDS = collections.OrderedDict([
      ('magic', 'I'),
      ('version', 'I'),
      ('img_version', '68s'),
      ('total_entries', 'I'),
      ('total_size', 'I'),
  ])

  def __init__(self,
               magic=FBPACK_MAGIC,
               version=FBPACK_VERSION_V1,
               img_version=b'',
               total_entries=0,
               total_size=0):
    super().__init__(magic, version, img_version, total_entries, total_size)

class PackEntryV1(packedstruct.PackedStruct):
  type: int
  name: str
  size_h: int
  size: int
  next_offset_h: int
  next_offset: int
  crc32: int
  _FIELDS = collections.OrderedDict([
      ('type', 'I'),
      ('name', '32s'),
      ('size_h', 'I'),
      ('size', 'I'),
      ('next_offset_h', 'I'),
      ('next_offset', 'I'),
      ('crc32', 'I'),
  ])

  # Provide defaults.
  # pylint: disable=useless-super-delegation
  def __init__(self,
               type_=0,
               name=b'',
               size_h=0,
               size=0,
               next_offset_h=0,
               next_offset=0,
               crc32=0):
    super().__init__(type_, name, size_h, size, next_offset_h, next_offset, crc32)

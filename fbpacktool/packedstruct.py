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
#
import collections
import struct


class PackedStruct(object):
  """Class representing a C style packed structure.

  Derived classes need to provide a dictionary where the keys are the attributes
  and the values are the format characters for each field. e.g.

  class Foo(PackedStruct):
      _FIELDS = {
          x: 'I',
          name: '64s',
      }

  In this case Foo.x will represent an "unsigned int" C value, while Foo.name
  will be a "char[64]" C value.
  """
  _FIELDS: collections.OrderedDict

  def __init__(self, *args, **kwargs):
    self._fmt = '<' + ''.join(fmt for fmt in self._FIELDS.values())
    for name in self._FIELDS:
      setattr(self, name, None)

    for name, val in zip(self._FIELDS.keys(), args):
      setattr(self, name, val)
    for name, val in kwargs.items():
      setattr(self, name, val)

  def __repr__(self):
    return '{} {{\n'.format(self.__class__.__name__) + ',\n'.join(
        '    {!r}: {!r}'.format(k, getattr(self, k))
        for k in self._FIELDS) + '\n}'

  def __str__(self):
    return struct.pack(self._fmt, *(getattr(self, x) for x in self._FIELDS))

  def __bytes__(self):
    return struct.pack(self._fmt, *(getattr(self, x) for x in self._FIELDS))

  def __len__(self):
    return struct.calcsize(self._fmt)

  @classmethod
  def from_bytes(cls, data):
    fmt_str = '<' + ''.join(fmt for fmt in cls._FIELDS.values())
    return cls(*struct.unpack(fmt_str, data))

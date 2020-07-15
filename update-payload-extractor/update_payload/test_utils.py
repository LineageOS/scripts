#
# Copyright (C) 2013 The Android Open Source Project
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

"""Utilities for unit testing."""

from __future__ import absolute_import
from __future__ import print_function

import io
import hashlib
import os
import struct
import subprocess

from update_payload import common
from update_payload import payload
from update_payload import update_metadata_pb2


class TestError(Exception):
  """An error during testing of update payload code."""


# Private/public RSA keys used for testing.
_PRIVKEY_FILE_NAME = os.path.join(os.path.dirname(__file__),
                                  'payload-test-key.pem')
_PUBKEY_FILE_NAME = os.path.join(os.path.dirname(__file__),
                                 'payload-test-key.pub')


def KiB(count):
  return count << 10


def MiB(count):
  return count << 20


def GiB(count):
  return count << 30


def _WriteInt(file_obj, size, is_unsigned, val):
  """Writes a binary-encoded integer to a file.

  It will do the correct conversion based on the reported size and whether or
  not a signed number is expected. Assumes a network (big-endian) byte
  ordering.

  Args:
    file_obj: a file object
    size: the integer size in bytes (2, 4 or 8)
    is_unsigned: whether it is signed or not
    val: integer value to encode

  Raises:
    PayloadError if a write error occurred.
  """
  try:
    file_obj.write(struct.pack(common.IntPackingFmtStr(size, is_unsigned), val))
  except IOError as e:
    raise payload.PayloadError('error writing to file (%s): %s' %
                               (file_obj.name, e))


def _SetMsgField(msg, field_name, val):
  """Sets or clears a field in a protobuf message."""
  if val is None:
    msg.ClearField(field_name)
  else:
    setattr(msg, field_name, val)


def SignSha256(data, privkey_file_name):
  """Signs the data's SHA256 hash with an RSA private key.

  Args:
    data: the data whose SHA256 hash we want to sign
    privkey_file_name: private key used for signing data

  Returns:
    The signature string, prepended with an ASN1 header.

  Raises:
    TestError if something goes wrong.
  """
  data_sha256_hash = common.SIG_ASN1_HEADER + hashlib.sha256(data).digest()
  sign_cmd = ['openssl', 'rsautl', '-sign', '-inkey', privkey_file_name]
  try:
    sign_process = subprocess.Popen(sign_cmd, stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE)
    sig, _ = sign_process.communicate(input=data_sha256_hash)
  except Exception as e:
    raise TestError('signing subprocess failed: %s' % e)

  return sig


class SignaturesGenerator(object):
  """Generates a payload signatures data block."""

  def __init__(self):
    self.sigs = update_metadata_pb2.Signatures()

  def AddSig(self, version, data):
    """Adds a signature to the signature sequence.

    Args:
      version: signature version (None means do not assign)
      data: signature binary data (None means do not assign)
    """
    sig = self.sigs.signatures.add()
    if version is not None:
      sig.version = version
    if data is not None:
      sig.data = data

  def ToBinary(self):
    """Returns the binary representation of the signature block."""
    return self.sigs.SerializeToString()


class PayloadGenerator(object):
  """Generates an update payload allowing low-level control.

  Attributes:
    manifest: the protobuf containing the payload manifest
    version: the payload version identifier
    block_size: the block size pertaining to update operations

  """

  def __init__(self, version=1):
    self.manifest = update_metadata_pb2.DeltaArchiveManifest()
    self.version = version
    self.block_size = 0

  @staticmethod
  def _WriteExtent(ex, val):
    """Returns an Extent message."""
    start_block, num_blocks = val
    _SetMsgField(ex, 'start_block', start_block)
    _SetMsgField(ex, 'num_blocks', num_blocks)

  @staticmethod
  def _AddValuesToRepeatedField(repeated_field, values, write_func):
    """Adds values to a repeated message field."""
    if values:
      for val in values:
        new_item = repeated_field.add()
        write_func(new_item, val)

  @staticmethod
  def _AddExtents(extents_field, values):
    """Adds extents to an extents field."""
    PayloadGenerator._AddValuesToRepeatedField(
        extents_field, values, PayloadGenerator._WriteExtent)

  def SetBlockSize(self, block_size):
    """Sets the payload's block size."""
    self.block_size = block_size
    _SetMsgField(self.manifest, 'block_size', block_size)

  def SetPartInfo(self, part_name, is_new, part_size, part_hash):
    """Set the partition info entry.

    Args:
      part_name: The name of the partition.
      is_new: Whether to set old (False) or new (True) info.
      part_size: The partition size (in fact, filesystem size).
      part_hash: The partition hash.
    """
    partition = next((x for x in self.manifest.partitions
                      if x.partition_name == part_name), None)
    if partition is None:
      partition = self.manifest.partitions.add()
      partition.partition_name = part_name

    part_info = (partition.new_partition_info if is_new
                 else partition.old_partition_info)
    _SetMsgField(part_info, 'size', part_size)
    _SetMsgField(part_info, 'hash', part_hash)

  def AddOperation(self, part_name, op_type, data_offset=None,
                   data_length=None, src_extents=None, src_length=None,
                   dst_extents=None, dst_length=None, data_sha256_hash=None):
    """Adds an InstallOperation entry."""
    partition = next((x for x in self.manifest.partitions
                      if x.partition_name == part_name), None)
    if partition is None:
      partition = self.manifest.partitions.add()
      partition.partition_name = part_name

    operations = partition.operations
    op = operations.add()
    op.type = op_type

    _SetMsgField(op, 'data_offset', data_offset)
    _SetMsgField(op, 'data_length', data_length)

    self._AddExtents(op.src_extents, src_extents)
    _SetMsgField(op, 'src_length', src_length)

    self._AddExtents(op.dst_extents, dst_extents)
    _SetMsgField(op, 'dst_length', dst_length)

    _SetMsgField(op, 'data_sha256_hash', data_sha256_hash)

  def SetSignatures(self, sigs_offset, sigs_size):
    """Set the payload's signature block descriptors."""
    _SetMsgField(self.manifest, 'signatures_offset', sigs_offset)
    _SetMsgField(self.manifest, 'signatures_size', sigs_size)

  def SetMinorVersion(self, minor_version):
    """Set the payload's minor version field."""
    _SetMsgField(self.manifest, 'minor_version', minor_version)

  def _WriteHeaderToFile(self, file_obj, manifest_len):
    """Writes a payload heaer to a file."""
    # We need to access protected members in Payload for writing the header.
    # pylint: disable=W0212
    file_obj.write(payload.Payload._PayloadHeader._MAGIC)
    _WriteInt(file_obj, payload.Payload._PayloadHeader._VERSION_SIZE, True,
              self.version)
    _WriteInt(file_obj, payload.Payload._PayloadHeader._MANIFEST_LEN_SIZE, True,
              manifest_len)

  def WriteToFile(self, file_obj, manifest_len=-1, data_blobs=None,
                  sigs_data=None, padding=None):
    """Writes the payload content to a file.

    Args:
      file_obj: a file object open for writing
      manifest_len: manifest len to dump (otherwise computed automatically)
      data_blobs: a list of data blobs to be concatenated to the payload
      sigs_data: a binary Signatures message to be concatenated to the payload
      padding: stuff to dump past the normal data blobs provided (optional)
    """
    manifest = self.manifest.SerializeToString()
    if manifest_len < 0:
      manifest_len = len(manifest)
    self._WriteHeaderToFile(file_obj, manifest_len)
    file_obj.write(manifest)
    if data_blobs:
      for data_blob in data_blobs:
        file_obj.write(data_blob)
    if sigs_data:
      file_obj.write(sigs_data)
    if padding:
      file_obj.write(padding)


class EnhancedPayloadGenerator(PayloadGenerator):
  """Payload generator with automatic handling of data blobs.

  Attributes:
    data_blobs: a list of blobs, in the order they were added
    curr_offset: the currently consumed offset of blobs added to the payload
  """

  def __init__(self):
    super(EnhancedPayloadGenerator, self).__init__()
    self.data_blobs = []
    self.curr_offset = 0

  def AddData(self, data_blob):
    """Adds a (possibly orphan) data blob."""
    data_length = len(data_blob)
    data_offset = self.curr_offset
    self.curr_offset += data_length
    self.data_blobs.append(data_blob)
    return data_length, data_offset

  def AddOperationWithData(self, part_name, op_type, src_extents=None,
                           src_length=None, dst_extents=None, dst_length=None,
                           data_blob=None, do_hash_data_blob=True):
    """Adds an install operation and associated data blob.

    This takes care of obtaining a hash of the data blob (if so instructed)
    and appending it to the internally maintained list of blobs, including the
    necessary offset/length accounting.

    Args:
      part_name: The name of the partition (e.g. kernel or root).
      op_type: one of REPLACE, REPLACE_BZ, REPLACE_XZ.
      src_extents: list of (start, length) pairs indicating src block ranges
      src_length: size of the src data in bytes (needed for diff operations)
      dst_extents: list of (start, length) pairs indicating dst block ranges
      dst_length: size of the dst data in bytes (needed for diff operations)
      data_blob: a data blob associated with this operation
      do_hash_data_blob: whether or not to compute and add a data blob hash
    """
    data_offset = data_length = data_sha256_hash = None
    if data_blob is not None:
      if do_hash_data_blob:
        data_sha256_hash = hashlib.sha256(data_blob).digest()
      data_length, data_offset = self.AddData(data_blob)

    self.AddOperation(part_name, op_type, data_offset=data_offset,
                      data_length=data_length, src_extents=src_extents,
                      src_length=src_length, dst_extents=dst_extents,
                      dst_length=dst_length, data_sha256_hash=data_sha256_hash)

  def WriteToFileWithData(self, file_obj, sigs_data=None,
                          privkey_file_name=None, padding=None):
    """Writes the payload content to a file, optionally signing the content.

    Args:
      file_obj: a file object open for writing
      sigs_data: signatures blob to be appended to the payload (optional;
                 payload signature fields assumed to be preset by the caller)
      privkey_file_name: key used for signing the payload (optional; used only
                         if explicit signatures blob not provided)
      padding: stuff to dump past the normal data blobs provided (optional)

    Raises:
      TestError: if arguments are inconsistent or something goes wrong.
    """
    sigs_len = len(sigs_data) if sigs_data else 0

    # Do we need to generate a genuine signatures blob?
    do_generate_sigs_data = sigs_data is None and privkey_file_name

    if do_generate_sigs_data:
      # First, sign some arbitrary data to obtain the size of a signature blob.
      fake_sig = SignSha256(b'fake-payload-data', privkey_file_name)
      fake_sigs_gen = SignaturesGenerator()
      fake_sigs_gen.AddSig(1, fake_sig)
      sigs_len = len(fake_sigs_gen.ToBinary())

      # Update the payload with proper signature attributes.
      self.SetSignatures(self.curr_offset, sigs_len)

    if do_generate_sigs_data:
      # Once all payload fields are updated, dump and sign it.
      temp_payload_file = io.BytesIO()
      self.WriteToFile(temp_payload_file, data_blobs=self.data_blobs)
      sig = SignSha256(temp_payload_file.getvalue(), privkey_file_name)
      sigs_gen = SignaturesGenerator()
      sigs_gen.AddSig(1, sig)
      sigs_data = sigs_gen.ToBinary()
      assert len(sigs_data) == sigs_len, 'signature blob lengths mismatch'

    # Dump the whole thing, complete with data and signature blob, to a file.
    self.WriteToFile(file_obj, data_blobs=self.data_blobs, sigs_data=sigs_data,
                     padding=padding)

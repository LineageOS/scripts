#!/usr/bin/env python3
#adopted from https://pastebin.com/raw/qYcvaWyX

import base64
import os
import sys

from OpenSSL import crypto


def get_certificates(self):
    from OpenSSL.crypto import X509
    from OpenSSL._util import ffi as _ffi, lib as _lib
    certs = _ffi.NULL
    if self.type_is_signed():
       certs = self._pkcs7.d.sign.cert
    elif self.type_is_signedAndEnveloped():
        certs = self._pkcs7.d.signed_and_enveloped.cert

    pycerts = []
    for i in range(_lib.sk_X509_num(certs)):
        pycert = X509.__new__(X509)
        pycert._x509 = _lib.sk_X509_value(certs, i)
        pycerts.append(pycert)
    if not pycerts:
        return None
    return tuple(pycerts)

crypto.PKCS7.get_certificates = get_certificates



if len(sys.argv) != 2:
    print("Usage: python verify.py <filename>")
    sys.exit(0)

f = open(sys.argv[1], 'rb')
file_size = os.stat(sys.argv[1]).st_size
f.seek(file_size - 6)
footer = f.read(6)

if footer[2] != ord(b'\xff') or footer[3] != ord(b'\xff'):
    print("no signature in file (no footer)")
    sys.exit(-1)

commentSize = (footer[4] & 255) | ((footer[5] & 255) <<8)
signatureStart = (footer[0] & 255) | ((footer[1] & 255) << 8)

f.seek(file_size - (commentSize + 22));
eocd = bytearray(f.read())

if eocd[0] != ord(b'\x50') or eocd[1] != ord(b'\x4b') or eocd[2] != ord(b'\x05') or eocd[3] != ord(b'\x06'):
    print("no signature in file (bad eocd)")
    sys.exit(-1)

for i in range(5, len(eocd)-4):
    if eocd[i] == ord(b'\x50') and eocd[i+1] == ord(b'\x4b') and eocd[i+2] == ord(b'\x05') and eocd[i+3] == ord(b'\x06'):
        print("EOCD marker found after start of EOCD")
        sys.exit(-1)

block = eocd[commentSize+22-signatureStart:commentSize+22]

decoded = "-----BEGIN CERTIFICATE-----\n" + base64.b64encode(block).decode('ascii') + "\n-----END CERTIFICATE-----"

PKCS7 = crypto.load_pkcs7_data(crypto.FILETYPE_PEM, decoded)

cert = PKCS7.get_certificates()[0]

print("Certificate Fingerprints:")

print("\tMD5: {}".format(cert.digest('md5').decode("utf-8")))
print("\tSHA1: {}".format(cert.digest("sha1").decode("utf-8")))
print("\tSHA256: {}".format(cert.digest("sha256").decode("utf-8")))

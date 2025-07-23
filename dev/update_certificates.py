#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import base64
import xml.etree.ElementTree as ET
from argparse import ArgumentParser
from pathlib import Path
from typing import Dict, Optional

from cryptography import x509

from utils.utils import android_root

EXCLUDED_DIRS = set(
    [
        'out',
        'system',
    ]
)

MAC_PERMISSIONS_PATTERN = '*mac_permissions.xml'


def find_glob(dir_path: str, pattern: str):
    for child_dir in Path(dir_path).iterdir():
        if not child_dir.is_dir():
            continue

        if child_dir.name in EXCLUDED_DIRS:
            continue

        for xml in child_dir.rglob(pattern):
            yield xml


def read_mac_permission_xml(
    mac_permission_xml: Path,
    name_cert_map: Dict[str, str],
):
    tree = ET.parse(mac_permission_xml)

    for signer in tree.findall('signer'):
        signature = signer.get('signature')
        if signature is None:
            continue

        package = signer.find('package')
        if package is not None:
            name = package.get('name')
            print(f'Pacakge certificate not supported: {name}')
            continue

        seinfo = signer.find('seinfo')
        if seinfo is None:
            continue

        seinfo_value = seinfo.get('value')
        if seinfo_value is None:
            continue

        name_cert_map[seinfo_value] = signature


def read_keys_conf(keys_conf: Path, token_path_map: Dict[str, str]):
    token = None

    for line in keys_conf.read_text().splitlines():
        if line.startswith('#'):
            continue

        if not line:
            continue

        if line.startswith('['):
            assert line.endswith(']')
            token = line[1:-1]
            continue

        ALL = 'ALL : '
        assert line.startswith(ALL)
        cert_path = line[len(ALL) :]

        assert token is not None
        token_path_map[token] = cert_path


def get_cert_format(cert_path: Path):
    original_cert_lines = cert_path.read_bytes().splitlines()
    line_length = 0
    start_line = None
    end_line = None
    for line in original_cert_lines:
        if line.startswith(b'-'):
            if start_line is None:
                start_line = line
            elif end_line is None:
                end_line = line
            else:
                assert False

            continue

        assert start_line is not None
        assert end_line is None

        line_length = max(line_length, len(line))

    assert start_line is not None
    assert end_line is not None

    return start_line, end_line, line_length


def chunk_bytes(data: bytes, chunk_size: int):
    for i in range(0, len(data), chunk_size):
        yield data[i : i + chunk_size]


def format_cert(
    cert: str,
    start_line: bytes,
    end_line: bytes,
    line_length: int,
):
    decoded_cert = bytes.fromhex(cert)

    # Validate once after readin
    certificate = x509.load_der_x509_certificate(decoded_cert)

    # Replace newlines and validate again
    base64_encoded_cert = base64.encodebytes(decoded_cert)
    base64_encoded_cert = base64_encoded_cert.replace(b'\n', b'')

    decoded_cert = base64.decodebytes(base64_encoded_cert)
    certificate = x509.load_der_x509_certificate(decoded_cert)

    pem_cert = b''
    pem_cert += start_line
    pem_cert += b'\n'
    for chunk in chunk_bytes(base64_encoded_cert, line_length):
        pem_cert += chunk
        pem_cert += b'\n'
    pem_cert += end_line
    pem_cert += b'\n'

    # Validate PEM format
    certificate = x509.load_pem_x509_certificate(pem_cert)

    return certificate, pem_cert


def update_certificates():
    parser = ArgumentParser(
        prog='update_certificates.py',
        description='Update app certificates',
    )
    parser.add_argument(
        '-t',
        '--target',
        action='store',
        help='Android root sub-directory in which to update certificates',
    )
    parser.add_argument(
        'source',
        action='store',
        help='Path to directory containing mac_permissions.xml '
        ' files from which to update certificates',
    )

    args = parser.parse_args()

    source_dir: str = args.source
    target_dir: Optional[str] = args.target
    if target_dir is None:
        target_dir = android_root

    # Read seinfo values and signature
    name_cert_map: Dict[str, str] = {}
    for mac_permission_xml in find_glob(source_dir, MAC_PERMISSIONS_PATTERN):
        read_mac_permission_xml(mac_permission_xml, name_cert_map)

    # Read seinfo and @TOKEN name to be found in keys.conf
    name_token_map: Dict[str, str] = {}
    for mac_permission_xml in find_glob(target_dir, MAC_PERMISSIONS_PATTERN):
        read_mac_permission_xml(mac_permission_xml, name_token_map)

    token_path_map: Dict[str, str] = {}
    for keys_conf in find_glob(target_dir, 'keys.conf'):
        read_keys_conf(keys_conf, token_path_map)

    for name, cert in name_cert_map.items():
        if name not in name_token_map:
            continue

        token = name_token_map[name]
        if token not in token_path_map:
            continue

        cert_path = token_path_map[token]
        full_cert_path = Path(android_root, cert_path)

        start_line, end_line, line_length = get_cert_format(full_cert_path)
        certificate, pem_cert = format_cert(
            cert,
            start_line,
            end_line,
            line_length,
        )

        print(f'Writing cert for app: {name}, token: {token} at {cert_path}')
        print(f'Subject: {certificate.subject.rfc4514_string()}')
        print(f'Issuer: {certificate.issuer.rfc4514_string()}')
        print(f'Serial number: {certificate.serial_number}')
        print(f'Valid from: {certificate.not_valid_before_utc}')
        print(f'Valid until: {certificate.not_valid_after_utc}')

        with open(full_cert_path, 'wb') as o:
            o.write(pem_cert)


if __name__ == '__main__':
    update_certificates()

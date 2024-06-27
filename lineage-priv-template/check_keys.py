#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# SPDX-FileCopyrightText: 2024 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

import glob
import subprocess
import sys
from zipfile import ZipFile

from cryptography import x509

OUT = sys.argv[1]
KNOWN_KEYS = [
    x509.load_pem_x509_certificate(open(f, "rb").read()).public_key()
    for f in glob.glob("*.x509.pem")
]


def check_public_key(path: str) -> None:
    certs = []
    stdout = subprocess.run(
        [
            "java",
            "-jar",
            "../../../prebuilts/sdk/tools/linux/lib/apksigner.jar",
            "verify",
            "--print-certs-pem",
            path,
        ],
        capture_output=True,
    ).stdout

    while begin := stdout.find(b"-----BEGIN CERTIFICATE-----"):
        end = stdout.find(b"-----END CERTIFICATE-----", begin)

        if end == -1:
            break

        certs.append(x509.load_pem_x509_certificate(stdout[begin : end + 25]))
        stdout = stdout[end + 25:]

    if not any(x.public_key() in KNOWN_KEYS for x in certs):
        print(path, "is signed with an unknown key!")


[check_public_key(f) for f in glob.glob(f"{OUT}/obj/**/*.apk", recursive=True)]
[check_public_key(f) for f in glob.glob(f"{OUT}/obj/**/*.apex", recursive=True)]
[check_public_key(f) for f in glob.glob(f"{OUT}/obj/**/*.capex", recursive=True)]

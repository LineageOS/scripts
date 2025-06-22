#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# SPDX-FileCopyrightText: 2024-2025 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

import glob
import os
import subprocess
import sys
from multiprocessing import Pool

from cryptography import x509

KNOWN_KEYS = [
    x509.load_pem_x509_certificate(open(f, "rb").read()).public_key()
    for f in glob.glob("*.x509.pem")
]


def check_public_key(path: str) -> None:
    if not os.path.isfile(path):
        return

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
        stdout = stdout[end + 25 :]

    if not any(x.public_key() in KNOWN_KEYS for x in certs):
        print(path, "is signed with an unknown key!")


def main():
    out = sys.argv[1]

    with Pool(8) as pool:
        pool.map(
            check_public_key,
            (
                glob.glob(f"{out}/obj/**/*.apk", recursive=True)
                + glob.glob(f"{out}/obj/**/*.apex", recursive=True)
                + glob.glob(f"{out}/obj/**/*.capex", recursive=True)
            ),
        )


if __name__ == "__main__":
    main()

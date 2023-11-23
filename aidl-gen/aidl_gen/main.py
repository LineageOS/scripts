#
# Copyright (C) 2023 The LineageOS Project
#
# SPDX-License-Identifier: Apache-2.0
#

from aidl_gen.aidl.package import Package
from aidl_gen.aidl.service import AIDLService
from argparse import ArgumentParser
from pathlib import Path

def main():
    parser = ArgumentParser(prog="aidl_gen")

    parser.add_argument("fqname", type=str,
                        help="Full qualifier of an AIDL interface (e.g. android.hardware.light.ILights)")
    parser.add_argument("version", type=int, required=False,
                        help="Version of the AIDL interface (e.g. 1), if not specified, the highest one will be used")
    parser.add_argument("-I", "--include", type=Path, action='append', required=True,
                        help="Folders to include that contains the AIDL interface "
                             "(note: use the folder where Android.bp resides, aka the top AIDL "
                             "folder), you can use multiple -I flags to include multiple "
                             "locations, but at least one is required")
    parser.add_argument("out_dir", type=Path,
                        help="Folders where the service will be written on")

    args = parser.parse_args()

    # TODO: support for nested interfaces
    package_name, _ = args.fqname.rsplit('.', 1)

    package = Package.find_package(package_name, args.include)
    versions = package.get_versions()
    version: int = args.version if args.version is int else max(versions)

    assert version in versions, f"Version {version} is not available for {args.fqname}"

    

    service = AIDLService(args.fqname, args.include)
    service.write_to_folder(args.out_dir)

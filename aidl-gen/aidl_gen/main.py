#
# Copyright (C) 2023 The LineageOS Project
#
# SPDX-License-Identifier: Apache-2.0
#

from argparse import ArgumentParser
from pathlib import Path

from aidl_gen.aidl.backend import Backend
from aidl_gen.aidl.package import Package
from aidl_gen.formatter import get_formatter

def main():
    parser = ArgumentParser(prog="aidl_gen")

    parser.add_argument(
        "fqname", type=str,
        help="Full qualifier of an AIDL interface (e.g. android.hardware.light.ILights)"
    )
    parser.add_argument(
        "out_dir", type=Path, help="Folders where the service will be written on"
    )
    parser.add_argument(
        "-v", "--version", type=int,
        help="Version of the AIDL interface (e.g. 1), if not specified, "
             "the highest one available will be used"
    )
    parser.add_argument(
        "-b", "--backend", type=Backend, choices=list(Backend), default=Backend.RUST,
        help="Backend to use for the generated service (default: rust). "
             "Note: Java and C++ backends are for system services, NDK and Rust "
             "are for vendor services"
    )
    parser.add_argument(
        "-I", "--include", type=Path, action='append', required=True,
        help="Folders to include that contains the AIDL interface "
             "(note: use the folder where Android.bp resides, aka the top AIDL "
             "folder), you can use multiple -I flags to include multiple "
             "locations, but at least one is required"
    )

    args = parser.parse_args()

    # Check arguments
    assert args.version is None or args.version > 0, f"Invalid version {args.version}"
    for include in args.include:
        assert include.is_dir(), f"{include} is not a directory"
    assert args.out_dir.is_dir(), f"{args.out_dir} is not a directory"

    # TODO: support for nested interfaces
    package_name, _ = args.fqname.rsplit('.', 1)

    package = Package.find_package(package_name, args.include)
    versions = package.get_versions()
    version: int = args.version if args.version is int else max(versions)

    assert version in versions, f"Version {version} is not available for {args.fqname}"

    aidl_interface = package.get_aidl_interface_for_version(version)

    interface = aidl_interface.get_interface(args.fqname, args.include)

    formatter = get_formatter(args.backend)

    formatter.dump_to_folder(package, aidl_interface, interface, args.out_dir)

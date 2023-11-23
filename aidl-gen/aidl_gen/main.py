#
# Copyright (C) 2023 The LineageOS Project
#
# SPDX-License-Identifier: Apache-2.0
#

from argparse import ArgumentParser
from pathlib import Path

from aidl_gen.aidl.interface import Interface
from aidl_gen.aidl.package import Package
from aidl_gen.formatter import get_formatter
from aidl_gen.formatter.backend import Backend
from aidl_gen.parser import Parser

def main():
    argument_parser = ArgumentParser(prog="aidl_gen")

    argument_parser.add_argument(
        "fqname", type=str,
        help="Full qualifier of an AIDL interface (e.g. android.hardware.light.ILights)"
    )
    argument_parser.add_argument(
        "out_dir", type=Path, help="Folders where the service will be written on"
    )
    argument_parser.add_argument(
        "-v", "--version", type=int,
        help="Version of the AIDL interface (e.g. 1), if not specified, "
             "the highest one available will be used"
    )
    argument_parser.add_argument(
        "-b", "--backend", type=Backend, choices=list(Backend), default=Backend.RUST,
        help="Backend to use for the generated service (default: rust). "
             "Note: Java and C++ backends are for system services, NDK and Rust "
             "are for vendor services"
    )
    argument_parser.add_argument(
        "-I", "--include", type=Path, action='append', required=True,
        help="Folders to include that contains the AIDL interface "
             "(note: use the folder where Android.bp resides, aka the top AIDL "
             "folder), you can use multiple -I flags to include multiple "
             "locations, but at least one is required"
    )

    args = argument_parser.parse_args()

    # Check arguments
    assert args.version is None or args.version > 0, f"Invalid version {args.version}"
    for include in args.include:
        assert include.is_dir(), f"{include} is not a directory"
    assert args.out_dir.is_dir(), f"{args.out_dir} is not a directory"

    # TODO: support for nested interfaces
    package_name, _ = args.fqname.rsplit('.', 1)

    package = Package.find_package(package_name, args.include)

    # Get the highest version if not specified
    versions = package.get_versions()
    version: int = args.version if args.version is int else max(versions)
    assert version in versions, f"Version {version} is not available for {args.fqname}"

    # Import the AIDL interface
    parser = Parser(args.include)

    aidl_object = parser.import_aidl(args.fqname, version)
    assert aidl_object is not None, f"{args.fqname} not found in {package}, version {version}"
    assert isinstance(aidl_object, Interface), f"{args.fqname} is not an interface"

    # Dump to folder
    formatter = get_formatter(args.backend)
    formatter.dump_to_folder(package, version, aidl_object, parser, args.out_dir)

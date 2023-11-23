#
# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0
#

from argparse import ArgumentParser
from pathlib import Path
from typing import List, Optional

from aidl_gen.aidl.interface import Interface
from aidl_gen.aidl.package import Package
from aidl_gen.formatter import get_formatter
from aidl_gen.formatter.backend import Backend
from aidl_gen.parser import Parser

def main():
    argument_parser = ArgumentParser(prog="aidl_gen")

    argument_parser.add_argument(
        "fqname",
        type=str,
        help="Full qualifier of an AIDL interface (e.g. android.hardware.light.ILights)",
    )
    argument_parser.add_argument(
        "-O", "--out",
        required=True,
        type=Path,
        help="Folders where the service will be written on",
    )
    argument_parser.add_argument(
        "-v", "--version",
        type=int,
        help="Version of the AIDL interface (e.g. 1), if not specified, "
             "the highest one available will be used",
    )
    argument_parser.add_argument(
        "-b", "--backend",
        type=Backend,
        choices=list(Backend),
        default=Backend.RUST,
        help="Backend to use for the generated service (default: rust)."
             " Note: Java and C++ backends are for system services, NDK and Rust"
             " are for vendor services",
    )
    argument_parser.add_argument(
        "-I", "--include",
        type=Path,
        action='append',
        required=True,
        help="Folders to include that contains the AIDL interface"
             " (note: use the folder where Android.bp resides, aka the top AIDL"
             " folder), you can use multiple -I flags to include multiple"
             " locations, but at least one is required",
    )

    args = argument_parser.parse_args()

    fqname: str = args.fqname
    out: Path = args.out
    version: Optional[int] = args.version
    backend: Backend = args.backend
    includes: List[Path] = args.include

    parser = Parser(includes)

    # Check arguments
    assert version is None or version > 0, f"Invalid version {version}"
    for include in includes:
        assert include.is_dir(), f"{include} is not a directory"
    assert out.is_dir(), f"{out} is not a directory"

    # TODO: support for nested interfaces
    package_name, _ = fqname.rsplit('.', 1)

    package = Package.find_package(package_name, includes)

    # Get the highest version if not specified
    versions = package.get_versions()
    version = version if version is not None else max(versions)
    assert version in versions, f"Version {version} is not available for {fqname}"

    # Import the AIDL interface
    aidl_object = parser.import_aidl(fqname, version)
    assert isinstance(aidl_object, Interface), f"{fqname} is not an interface"

    # Dump to folder
    formatter = get_formatter(backend)
    formatter.dump_to_folder(package, version, aidl_object, parser, out)

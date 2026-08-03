#!/usr/bin/env python3

# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

"""
Usage:
    sf_offsets_to_props.py <advanced_sf_offsets.xml> [--version N] [--fps 60,90,120]
                           [--base-sf NS --base-app NS] [--late-only] [--list]
"""
import argparse
import subprocess
import sys
import xml.etree.ElementTree as ET

MODES = ("early", "earlyGl", "late")


def adb_target_version(serial=None):
    """Read vendor.display.target.version from a connected device, or None."""
    cmd = ["adb"]
    if serial:
        cmd += ["-s", serial]
    cmd += ["shell", "getprop", "vendor.display.target.version"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    value = out.stdout.strip()
    if out.returncode != 0 or not value.isdigit():
        return None
    return int(value)


def parse_devices(root):
    devices = {}
    lst = root.find("DeviceSettingList")
    if lst is None:
        sys.exit("error: no <DeviceSettingList> in file")
    for dev in lst.findall("Device"):
        version = int(dev.get("version"))
        rows = {}
        for m in dev.findall("FpsOffsetMap"):
            fps = int(m.get("fps"))
            pct = int(m.get("SfDurationPercentage"))
            app = m.get("AppDuration")
            rows[fps] = (pct, int(app) if app is not None else None)
        devices[version] = rows
    default = lst.find("DefaultDevice")
    default_version = int(default.get("version")) if default is not None else None
    return devices, default_version


def sf_duration_ns(fps, pct):
    period = 10**9 // fps
    return round(period * pct / 100)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("xml", help="path to advanced_sf_offsets.xml")
    ap.add_argument("--version", type=int, default=None,
                    help="Device version to use (default: read vendor.display.target.version "
                         "from the device via adb, falling back to the XML's DefaultDevice)")
    ap.add_argument("--serial", default=None,
                    help="adb serial to query when auto-detecting the version")
    ap.add_argument("--fps", default=None,
                    help="comma-separated refresh rates to emit (default: all in the XML); "
                         "limit this to the rates the panel actually exposes")
    ap.add_argument("--base-sf", type=int, default=None,
                    help="also emit base debug.sf.*.sf.duration props with this value (ns)")
    ap.add_argument("--base-app", type=int, default=None,
                    help="also emit base debug.sf.*.app.duration props with this value (ns)")
    ap.add_argument("--late-only", action="store_true",
                    help="emit only late.* props (skip the early/earlyGl mirrors)")
    ap.add_argument("--list", action="store_true",
                    help="list device versions found in the XML and exit")
    args = ap.parse_args()

    root = ET.parse(args.xml).getroot()
    devices, default_version = parse_devices(root)

    if args.list:
        for version in sorted(devices):
            tag = "  (default)" if version == default_version else ""
            print(f"Device version {version}{tag}")
            for fps, (pct, app) in sorted(devices[version].items()):
                sf = sf_duration_ns(fps, pct)
                app_s = f"  app={app}" if app is not None else ""
                print(f"  {fps:>4} Hz: sf={sf} ({pct}% of period){app_s}")
        return

    version = args.version
    if version is None:
        version = adb_target_version(args.serial)
        if version is not None:
            print(f"# note: using vendor.display.target.version={version} from device",
                  file=sys.stderr)
    if version is None:
        version = default_version
        if version is not None:
            print(f"# note: no device reachable via adb - using DefaultDevice "
                  f"version {version} from the XML", file=sys.stderr)
    if version is None:
        sys.exit("error: no --version given, no device via adb, and no <DefaultDevice> in file")
    if version not in devices:
        sys.exit(f"error: Device version {version} not in file (have: {sorted(devices)})")

    rows = devices[version]
    if args.fps:
        wanted = [int(f) for f in args.fps.split(",")]
        missing = [f for f in wanted if f not in rows]
        if missing:
            print(f"# note: no XML entry for {missing} Hz - base props apply there",
                  file=sys.stderr)
        rows = {f: rows[f] for f in wanted if f in rows}

    modes = ("late",) if args.late_only else MODES
    print(f"# Generated from {args.xml} (Device version {version})")
    for mode in sorted(modes, key=str.lower):
        if args.base_app is not None:
            print(f"debug.sf.{mode}.app.duration={args.base_app}")
        for fps, (_, app) in sorted(rows.items()):
            if app is not None:
                print(f"debug.sf.{mode}.app.duration.{fps}={app}")
        if args.base_sf is not None:
            print(f"debug.sf.{mode}.sf.duration={args.base_sf}")
        for fps, (pct, _) in sorted(rows.items()):
            print(f"debug.sf.{mode}.sf.duration.{fps}={sf_duration_ns(fps, pct)}")


if __name__ == "__main__":
    main()

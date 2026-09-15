#!/usr/bin/env python3
# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

"""
Usage:
    sf_offsets_to_props.py [advanced_sf_offsets.xml] [--version N] [--fps 60,90,120]
                           [--base-sf NS --base-app NS] [--late-only] [--list]
                           [--early-sf-phase NS --early-gl-sf-phase NS]
                           [--late-app-phase NS --late-sf-phase NS]
"""

import argparse
import subprocess
import sys
import xml.etree.ElementTree as ET

MODES = ('early', 'earlyGl', 'late')
PHASE_MODES = {
    'early': 'early_sf',
    'earlyGl': 'early_gl_sf',
    'late': 'late_sf',
}


def adb_advanced_sf_offsets(serial=None):
    """Read advanced_sf_offsets.xml from a connected device, or None."""
    cmd = ['adb']
    if serial:
        cmd += ['-s', serial]
    cmd += ['shell', 'cat', '/vendor/etc/display/advanced_sf_offsets.xml']
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    return out.stdout


def adb_target_version(serial=None):
    """Read vendor.display.target.version from a connected device, or None."""
    cmd = ['adb']
    if serial:
        cmd += ['-s', serial]
    cmd += ['shell', 'getprop', 'vendor.display.target.version']
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
    lst = root.find('DeviceSettingList')
    if lst is None:
        sys.exit('error: no <DeviceSettingList> in file')
    for dev in lst.findall('Device'):
        version = int(dev.get('version'))
        rows = {}
        for m in dev.findall('FpsOffsetMap'):
            fps = int(m.get('fps'))
            duration_pct = m.get('SfDurationPercentage')
            if duration_pct is not None:
                pct = int(duration_pct)
            else:
                offset = m.get('advancedSfOffsetPercentage')
                if offset is None:
                    sys.exit(
                        f'error: no SF duration percentage for {fps} Hz in file'
                    )
                pct = 100 + int(offset)
            app = m.get('AppDuration')
            rows[fps] = (pct, int(app) if app is not None else None)
        devices[version] = rows
    default = lst.find('DefaultDevice')
    default_version = (
        int(default.get('version')) if default is not None else None
    )
    return devices, default_version


def sf_duration_ns(fps, pct):
    period = 10**9 // fps
    return round(period * pct / 100)


def vsync_period(fps):
    return 10**9 // fps


def app_duration_ns(fps, app_phase, sf_phase):
    period = vsync_period(fps)
    duration = period + sf_phase - app_phase
    if duration < period:
        duration += period
    return duration


def mode_durations(fps, row, mode, phases):
    period = vsync_period(fps)
    pct, app = row if row is not None else (None, None)

    if pct is not None:
        sf_phase = period - sf_duration_ns(fps, pct)
        if period < 15_000_000 and phases is not None:
            app_phase = phases['late_app']
        elif period >= 15_000_000 and phases is not None:
            app_phase = 1_000_000
        else:
            app_phase = None
    elif period >= 15_000_000:
        app_phase = 1_000_000
        sf_phase = 1_000_000
    else:
        app_phase = phases['late_app'] if phases is not None else None
        if phases is None:
            return app, None
        sf_phase = phases[PHASE_MODES[mode]]

    if app is None and app_phase is not None:
        app = app_duration_ns(fps, app_phase, sf_phase)
    return app, period - sf_phase


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('xml', nargs='?', help='path to advanced_sf_offsets.xml')
    ap.add_argument(
        '--version',
        type=int,
        default=None,
        help='Device version to use (default: read vendor.display.target.version '
        "from the device via adb, falling back to the XML's DefaultDevice)",
    )
    ap.add_argument(
        '--serial',
        default=None,
        help='adb serial to query when auto-detecting the version',
    )
    ap.add_argument(
        '--fps',
        default=None,
        help='comma-separated refresh rates to emit (default: all in the XML); '
        'limit this to the rates the panel actually exposes',
    )
    ap.add_argument(
        '--base-sf',
        type=int,
        default=None,
        help='also emit base debug.sf.*.sf.duration props with this value (ns)',
    )
    ap.add_argument(
        '--base-app',
        type=int,
        default=None,
        help='also emit base debug.sf.*.app.duration props with this value (ns)',
    )
    ap.add_argument(
        '--early-sf-phase',
        type=int,
        default=None,
        metavar='NS',
        help='debug.sf.high_fps_early_phase_offset_ns',
    )
    ap.add_argument(
        '--early-gl-sf-phase',
        type=int,
        default=None,
        metavar='NS',
        help='debug.sf.high_fps_early_gl_phase_offset_ns',
    )
    ap.add_argument(
        '--late-app-phase',
        type=int,
        default=None,
        metavar='NS',
        help='debug.sf.high_fps_late_app_phase_offset_ns',
    )
    ap.add_argument(
        '--late-sf-phase',
        type=int,
        default=None,
        metavar='NS',
        help='debug.sf.high_fps_late_sf_phase_offset_ns',
    )
    ap.add_argument(
        '--late-only',
        action='store_true',
        help='emit only late.* props (skip the early/earlyGl mirrors)',
    )
    ap.add_argument(
        '--list',
        action='store_true',
        help='list device versions found in the XML and exit',
    )
    args = ap.parse_args()

    phase_values = {
        'early_sf': args.early_sf_phase,
        'early_gl_sf': args.early_gl_sf_phase,
        'late_app': args.late_app_phase,
        'late_sf': args.late_sf_phase,
    }
    if any(value is not None for value in phase_values.values()):
        if not all(value is not None for value in phase_values.values()):
            sys.exit('error: all four phase offsets are required together')
        phases = phase_values
    else:
        phases = None

    if args.xml is not None:
        with open(args.xml) as f:
            advanced_sf_offsets_xml = f.read()
    else:
        advanced_sf_offsets_xml = adb_advanced_sf_offsets(args.serial)
        if advanced_sf_offsets_xml is not None:
            print(
                '# note: using advanced_sf_offsets.xml from device',
                file=sys.stderr,
            )
        else:
            sys.exit(
                'error: no advanced_sf_offsets.xml given and no device via adb to read it from'
            )

    root = ET.fromstring(advanced_sf_offsets_xml)
    devices, default_version = parse_devices(root)

    if args.list:
        for version in sorted(devices):
            tag = '  (default)' if version == default_version else ''
            print(f'Device version {version}{tag}')
            for fps, (pct, app) in sorted(devices[version].items()):
                sf = sf_duration_ns(fps, pct)
                app_s = f'  app={app}' if app is not None else ''
                print(f'  {fps:>4} Hz: sf={sf} ({pct}% of period){app_s}')
        return

    version = args.version
    if version is None:
        version = adb_target_version(args.serial)
        if version is not None:
            print(
                f'# note: using vendor.display.target.version={version} from device',
                file=sys.stderr,
            )
    if version is None:
        version = default_version
        if version is not None:
            print(
                f'# note: no device reachable via adb - using DefaultDevice '
                f'version {version} from the XML',
                file=sys.stderr,
            )
    if version is None:
        sys.exit(
            'error: no --version given, no device via adb, and no <DefaultDevice> in file'
        )
    if version not in devices:
        sys.exit(
            f'error: Device version {version} not in file (have: {sorted(devices)})'
        )

    rows = devices[version]
    if args.fps:
        wanted = [int(f) for f in args.fps.split(',')]
        missing = [f for f in wanted if f not in rows]
        if missing:
            print(
                f'# note: no XML entry for {missing} Hz - base props apply there',
                file=sys.stderr,
            )
        if phases is None:
            rows = {f: rows[f] for f in wanted if f in rows}
        else:
            rows = {f: rows.get(f) for f in wanted}
    if phases is not None:
        rows.setdefault(60, None)

    modes = ('late',) if args.late_only else MODES
    print(f'# Generated from {args.xml} (Device version {version})')
    for mode in sorted(modes, key=str.lower):
        base_app = args.base_app
        base_sf = args.base_sf
        if phases is not None:
            generated_app, generated_sf = mode_durations(
                60, rows.get(60), mode, phases
            )
            if base_app is None:
                base_app = generated_app
            if base_sf is None:
                base_sf = generated_sf
        if base_app is not None:
            print(f'debug.sf.{mode}.app.duration={base_app}')
        for fps, row in sorted(rows.items()):
            app, sf = mode_durations(fps, row, mode, phases)
            if app is not None:
                print(f'debug.sf.{mode}.app.duration.{fps}={app}')
        if base_sf is not None:
            print(f'debug.sf.{mode}.sf.duration={base_sf}')
        for fps, row in sorted(rows.items()):
            _, sf = mode_durations(fps, row, mode, phases)
            if sf is not None:
                print(f'debug.sf.{mode}.sf.duration.{fps}={sf}')


if __name__ == '__main__':
    main()

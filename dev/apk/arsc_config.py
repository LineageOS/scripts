# SPDX-FileCopyrightText: 2026 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from typing import List, Optional, Tuple

from apk.resource_types import ResTable_config
from apk.utils import str_from_c


def get_locale_qualifier(config: ResTable_config) -> str:
    assert not (bytes(config.language)[0] & 0x80), (
        'Packed 3-letter language codes not implemented'
    )

    assert not (bytes(config.country)[0] & 0x80), (
        'Packed 3-letter region codes not implemented'
    )

    language = str_from_c(config.language)
    if not language:
        return ''

    region = str_from_c(config.country)
    script = str_from_c(config.localeScript)
    variant = str_from_c(config.localeVariant)
    numbering = str_from_c(config.localeNumberingSystem)

    assert not script or not config.localeScriptWasComputed, (
        'Computed script handling not implemented'
    )

    if script or variant or numbering:
        tag = ['b', language]

        if script:
            tag.append(script)
        if region:
            tag.append(region)
        if variant:
            tag.append(variant)
        if numbering:
            tag.extend(['u', 'nu', numbering])

        return '+'.join(tag)

    return f'{language}-r{region}' if region else language


def decode_config_member(
    parts: List[str],
    value: int,
    values: List[Tuple[int, str]],
    mask: Optional[int] = None,
    ignore_value: Optional[int] = None,
    default_value_format: Optional[str] = None,
):
    if mask is not None:
        value = value & mask

    if ignore_value is not None and value == ignore_value:
        return

    for match_value, name in values:
        if value == match_value:
            parts.append(name)
            return

    if default_value_format is not None:
        name = default_value_format.format(value)
        parts.append(name)


def decode_config(config: ResTable_config):
    parts: List[str] = []

    if config.mcc:
        parts.append(f'mcc{config.mcc:03d}')

    if config.mnc:
        mnc = config.mnc
        if mnc == ResTable_config.MNC_ZERO:
            mnc = 0

        parts.append(f'mnc{mnc:02d}')

    locale = get_locale_qualifier(config)
    if locale:
        parts.append(locale)

    decode_config_member(
        parts,
        config.grammaticalInflection,
        [
            (ResTable_config.GRAMMATICAL_GENDER_NEUTER, 'neuter'),
            (ResTable_config.GRAMMATICAL_GENDER_FEMININE, 'feminine'),
            (ResTable_config.GRAMMATICAL_GENDER_MASCULINE, 'masculine'),
        ],
        mask=ResTable_config.GRAMMATICAL_INFLECTION_GENDER_MASK,
        ignore_value=0,
    )

    decode_config_member(
        parts,
        config.screenLayout,
        [
            (ResTable_config.LAYOUTDIR_LTR, 'ldltr'),
            (ResTable_config.LAYOUTDIR_RTL, 'ldrtl'),
        ],
        mask=ResTable_config.MASK_LAYOUTDIR,
        ignore_value=0,
        default_value_format='layoutDir={}',
    )

    if config.smallestScreenWidthDp:
        parts.append(f'sw{config.smallestScreenWidthDp}dp')

    if config.screenWidthDp:
        parts.append(f'w{config.screenWidthDp}dp')

    if config.screenHeightDp:
        parts.append(f'h{config.screenHeightDp}dp')

    decode_config_member(
        parts,
        config.screenLayout,
        [
            (ResTable_config.SCREENSIZE_SMALL, 'small'),
            (ResTable_config.SCREENSIZE_NORMAL, 'normal'),
            (ResTable_config.SCREENSIZE_LARGE, 'large'),
            (ResTable_config.SCREENSIZE_XLARGE, 'xlarge'),
        ],
        mask=ResTable_config.MASK_SCREENSIZE,
        ignore_value=ResTable_config.SCREENSIZE_ANY,
        default_value_format='screenLayoutSize={}',
    )

    decode_config_member(
        parts,
        config.screenLayout,
        [
            (ResTable_config.SCREENLONG_NO, 'notlong'),
            (ResTable_config.SCREENLONG_YES, 'long'),
        ],
        mask=ResTable_config.MASK_SCREENLONG,
        ignore_value=0,
        default_value_format='screenLayoutLong={}',
    )

    decode_config_member(
        parts,
        config.screenLayout2,
        [
            (ResTable_config.SCREENROUND_NO, 'notround'),
            (ResTable_config.SCREENROUND_YES, 'round'),
        ],
        mask=ResTable_config.MASK_SCREENROUND,
        ignore_value=0,
        default_value_format='screenRound={}',
    )

    decode_config_member(
        parts,
        config.colorMode,
        [
            (ResTable_config.WIDE_COLOR_GAMUT_NO, 'nowidecg'),
            (ResTable_config.WIDE_COLOR_GAMUT_YES, 'widecg'),
        ],
        mask=ResTable_config.MASK_WIDE_COLOR_GAMUT,
        ignore_value=0,
        default_value_format='wideColorGamut={}',
    )

    decode_config_member(
        parts,
        config.colorMode,
        [
            (ResTable_config.HDR_NO, 'lowdr'),
            (ResTable_config.HDR_YES, 'highdr'),
        ],
        mask=ResTable_config.MASK_HDR,
        ignore_value=0,
        default_value_format='hdr={}',
    )

    decode_config_member(
        parts,
        config.orientation,
        [
            (ResTable_config.ORIENTATION_PORT, 'port'),
            (ResTable_config.ORIENTATION_LAND, 'land'),
            (ResTable_config.ORIENTATION_SQUARE, 'square'),
        ],
        ignore_value=ResTable_config.ORIENTATION_ANY,
        default_value_format='orientation={}',
    )

    decode_config_member(
        parts,
        config.uiMode,
        [
            (ResTable_config.UI_MODE_TYPE_DESK, 'desk'),
            (ResTable_config.UI_MODE_TYPE_CAR, 'car'),
            (ResTable_config.UI_MODE_TYPE_TELEVISION, 'television'),
            (ResTable_config.UI_MODE_TYPE_APPLIANCE, 'appliance'),
            (ResTable_config.UI_MODE_TYPE_WATCH, 'watch'),
            (ResTable_config.UI_MODE_TYPE_VR_HEADSET, 'vrheadset'),
        ],
        mask=ResTable_config.MASK_UI_MODE_TYPE,
        ignore_value=ResTable_config.UI_MODE_TYPE_ANY,
        default_value_format='uiModeType={}',
    )

    decode_config_member(
        parts,
        config.uiMode,
        [
            (ResTable_config.UI_MODE_NIGHT_NO, 'notnight'),
            (ResTable_config.UI_MODE_NIGHT_YES, 'night'),
        ],
        mask=ResTable_config.MASK_UI_MODE_NIGHT,
        ignore_value=0,
        default_value_format='uiModeNight={}',
    )

    decode_config_member(
        parts,
        config.density,
        [
            (ResTable_config.DENSITY_LOW, 'ldpi'),
            (ResTable_config.DENSITY_MEDIUM, 'mdpi'),
            (ResTable_config.DENSITY_TV, 'tvdpi'),
            (ResTable_config.DENSITY_HIGH, 'hdpi'),
            (ResTable_config.DENSITY_XHIGH, 'xhdpi'),
            (ResTable_config.DENSITY_XXHIGH, 'xxhdpi'),
            (ResTable_config.DENSITY_XXXHIGH, 'xxxhdpi'),
            (ResTable_config.DENSITY_NONE, 'nodpi'),
            (ResTable_config.DENSITY_ANY, 'anydpi'),
        ],
        ignore_value=ResTable_config.DENSITY_DEFAULT,
        default_value_format='{}dpi',
    )

    decode_config_member(
        parts,
        config.touchscreen,
        [
            (ResTable_config.TOUCHSCREEN_NOTOUCH, 'notouch'),
            (ResTable_config.TOUCHSCREEN_FINGER, 'finger'),
            (ResTable_config.TOUCHSCREEN_STYLUS, 'stylus'),
        ],
        ignore_value=ResTable_config.TOUCHSCREEN_ANY,
        default_value_format='touchscreen={}',
    )

    decode_config_member(
        parts,
        config.inputFlags,
        [
            (ResTable_config.KEYSHIDDEN_NO, 'keysexposed'),
            (ResTable_config.KEYSHIDDEN_YES, 'keyshidden'),
            (ResTable_config.KEYSHIDDEN_SOFT, 'keyssoft'),
        ],
        mask=ResTable_config.MASK_KEYSHIDDEN,
    )

    decode_config_member(
        parts,
        config.keyboard,
        [
            (ResTable_config.KEYBOARD_NOKEYS, 'nokeys'),
            (ResTable_config.KEYBOARD_QWERTY, 'qwerty'),
            (ResTable_config.KEYBOARD_12KEY, '12key'),
        ],
        ignore_value=ResTable_config.KEYBOARD_ANY,
        default_value_format='keyboard={}',
    )

    decode_config_member(
        parts,
        config.inputFlags,
        [
            (ResTable_config.NAVHIDDEN_NO, 'navexposed'),
            (ResTable_config.NAVHIDDEN_YES, 'navhidden'),
        ],
        mask=ResTable_config.MASK_NAVHIDDEN,
        ignore_value=0,
        default_value_format='inputFlagsNavHidden={}',
    )

    decode_config_member(
        parts,
        config.navigation,
        [
            (ResTable_config.NAVIGATION_NONAV, 'nonav'),
            (ResTable_config.NAVIGATION_DPAD, 'dpad'),
            (ResTable_config.NAVIGATION_TRACKBALL, 'trackball'),
            (ResTable_config.NAVIGATION_WHEEL, 'wheel'),
        ],
        ignore_value=ResTable_config.NAVIGATION_ANY,
        default_value_format='navigation={}',
    )

    if config.screenSize:
        parts.append(f'{config.screenWidth}x{config.screenHeight}')

    if config.version:
        version = f'v{config.sdkVersion}'
        if config.minorVersion:
            version += f'.{config.minorVersion}'
        parts.append(version)

    return '-'.join(parts)

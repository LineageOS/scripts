# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

from ctypes import Structure, Union, c_bool, c_uint8, c_uint16, c_uint32

RES_NULL_TYPE = 0x0000
RES_STRING_POOL_TYPE = 0x0001
RES_TABLE_TYPE = 0x0002
RES_XML_TYPE = 0x0003

RES_XML_FIRST_CHUNK_TYPE = 0x0100
RES_XML_START_NAMESPACE_TYPE = 0x0100
RES_XML_END_NAMESPACE_TYPE = 0x0101
RES_XML_START_ELEMENT_TYPE = 0x0102
RES_XML_END_ELEMENT_TYPE = 0x0103
RES_XML_CDATA_TYPE = 0x0104
RES_XML_LAST_CHUNK_TYPE = 0x017F
RES_XML_RESOURCE_MAP_TYPE = 0x0180

RES_TABLE_PACKAGE_TYPE = 0x0200
RES_TABLE_TYPE_TYPE = 0x0201
RES_TABLE_TYPE_SPEC_TYPE = 0x0202
RES_TABLE_LIBRARY_TYPE = 0x0203
RES_TABLE_OVERLAYABLE_TYPE = 0x0204
RES_TABLE_OVERLAYABLE_POLICY_TYPE = 0x0205
RES_TABLE_STAGED_ALIAS_TYPE = 0x0206

APP_PACKAGE_ID = 0x7F
SYS_PACKAGE_ID = 0x01


class ResChunk_header(Structure):
    _fields_ = [
        ('type', c_uint16),
        ('headerSize', c_uint16),
        ('size', c_uint32),
    ]


class ResTable_header(Structure):
    _fields_ = [
        ('header', ResChunk_header),
        ('packageCount', c_uint32),
    ]


class ResStringPool_header(Structure):
    SORTED_FLAG = 1 << 0
    UTF8_FLAG = 1 << 8

    _fields_ = [
        ('header', ResChunk_header),
        ('stringCount', c_uint32),
        ('styleCount', c_uint32),
        ('flags', c_uint32),
        ('stringsStart', c_uint32),
        ('stylesStart', c_uint32),
    ]


class ResTable_package(Structure):
    _fields_ = [
        ('header', ResChunk_header),
        ('id', c_uint32),
        ('name', c_uint16 * 128),
        ('typeStrings', c_uint32),
        ('lastPublicType', c_uint32),
        ('keyStrings', c_uint32),
        ('lastPublicKey', c_uint32),
        ('typeIdOffset', c_uint32),
    ]


class _ImsiStruct(Structure):
    _fields_ = [
        ('mcc', c_uint16),
        ('mnc', c_uint16),
    ]


class _ImsiUnion(Union):
    _anonymous_ = ('s',)
    _fields_ = [
        ('s', _ImsiStruct),
        ('imsi', c_uint32),
    ]


class _LocaleStruct(Structure):
    _fields_ = [
        ('language', c_uint8 * 2),
        ('country', c_uint8 * 2),
    ]


class _LocaleUnion(Union):
    _anonymous_ = ('s',)
    _fields_ = [
        ('s', _LocaleStruct),
        ('locale', c_uint32),
    ]


class _ScreenTypeStruct(Structure):
    _fields_ = [
        ('orientation', c_uint8),
        ('touchscreen', c_uint8),
        ('density', c_uint16),
    ]


class _ScreenTypeUnion(Union):
    _anonymous_ = ('s',)
    _fields_ = [
        ('s', _ScreenTypeStruct),
        ('screenType', c_uint32),
    ]


class _InputStruct(Structure):
    _fields_ = [
        ('keyboard', c_uint8),
        ('navigation', c_uint8),
        ('inputFlags', c_uint8),
        ('inputFieldPad0', c_uint8),
    ]


class _InputBits(Structure):
    _fields_ = [
        ('input', c_uint32, 24),
        ('inputFullPad0', c_uint32, 8),
    ]


class _GrammaticalInflectionStruct(Structure):
    _fields_ = [
        ('grammaticalInflectionPad0', c_uint8 * 3),
        ('grammaticalInflection', c_uint8),
    ]


class _InputUnion(Union):
    _anonymous_ = ('a', 'b', 'c')
    _fields_ = [
        ('a', _InputStruct),
        ('b', _InputBits),
        ('c', _GrammaticalInflectionStruct),
    ]


class _InputContainer(Structure):
    _anonymous_ = ('u',)
    _fields_ = [
        ('u', _InputUnion),
    ]


class _ScreenSizeStruct(Structure):
    _fields_ = [
        ('screenWidth', c_uint16),
        ('screenHeight', c_uint16),
    ]


class _ScreenSizeUnion(Union):
    _anonymous_ = ('s',)
    _fields_ = [
        ('s', _ScreenSizeStruct),
        ('screenSize', c_uint32),
    ]


class _VersionStruct(Structure):
    _fields_ = [
        ('sdkVersion', c_uint16),
        ('minorVersion', c_uint16),
    ]


class _VersionUnion(Union):
    _anonymous_ = ('s',)
    _fields_ = [
        ('s', _VersionStruct),
        ('version', c_uint32),
    ]


class _ScreenConfigStruct(Structure):
    _fields_ = [
        ('screenLayout', c_uint8),
        ('uiMode', c_uint8),
        ('smallestScreenWidthDp', c_uint16),
    ]


class _ScreenConfigUnion(Union):
    _anonymous_ = ('s',)
    _fields_ = [
        ('s', _ScreenConfigStruct),
        ('screenConfig', c_uint32),
    ]


class _ScreenSizeDpStruct(Structure):
    _fields_ = [
        ('screenWidthDp', c_uint16),
        ('screenHeightDp', c_uint16),
    ]


class _ScreenSizeDpUnion(Union):
    _anonymous_ = ('s',)
    _fields_ = [
        ('s', _ScreenSizeDpStruct),
        ('screenSizeDp', c_uint32),
    ]


class _ScreenConfig2Struct(Structure):
    _fields_ = [
        ('screenLayout2', c_uint8),
        ('colorMode', c_uint8),
        ('screenConfigPad2', c_uint16),
    ]


class _ScreenConfig2Union(Union):
    _anonymous_ = ('s',)
    _fields_ = [
        ('s', _ScreenConfig2Struct),
        ('screenConfig2', c_uint32),
    ]


class ResTable_config(Structure):
    MNC_ZERO = 0xFFFF

    ORIENTATION_ANY = 0
    ORIENTATION_PORT = 1
    ORIENTATION_LAND = 2
    ORIENTATION_SQUARE = 3

    TOUCHSCREEN_ANY = 0
    TOUCHSCREEN_NOTOUCH = 1
    TOUCHSCREEN_STYLUS = 2
    TOUCHSCREEN_FINGER = 3

    DENSITY_DEFAULT = 0
    DENSITY_LOW = 120
    DENSITY_MEDIUM = 160
    DENSITY_TV = 213
    DENSITY_HIGH = 240
    DENSITY_XHIGH = 320
    DENSITY_XXHIGH = 480
    DENSITY_XXXHIGH = 640
    DENSITY_ANY = 0xFFFE
    DENSITY_NONE = 0xFFFF

    KEYBOARD_ANY = 0
    KEYBOARD_NOKEYS = 1
    KEYBOARD_QWERTY = 2
    KEYBOARD_12KEY = 3

    NAVIGATION_ANY = 0
    NAVIGATION_NONAV = 1
    NAVIGATION_DPAD = 2
    NAVIGATION_TRACKBALL = 3
    NAVIGATION_WHEEL = 4

    MASK_KEYSHIDDEN = 0x0003
    KEYSHIDDEN_ANY = 0
    KEYSHIDDEN_NO = 1
    KEYSHIDDEN_YES = 2
    KEYSHIDDEN_SOFT = 3

    MASK_NAVHIDDEN = 0x000C
    SHIFT_NAVHIDDEN = 2
    NAVHIDDEN_ANY = 0 << 2
    NAVHIDDEN_NO = 1 << 2
    NAVHIDDEN_YES = 2 << 2

    GRAMMATICAL_GENDER_ANY = 0
    GRAMMATICAL_GENDER_NEUTER = 1
    GRAMMATICAL_GENDER_FEMININE = 2
    GRAMMATICAL_GENDER_MASCULINE = 3
    GRAMMATICAL_INFLECTION_GENDER_MASK = 0b11

    SCREENWIDTH_ANY = 0

    SCREENHEIGHT_ANY = 0

    SDKVERSION_ANY = 0

    MINORVERSION_ANY = 0

    MASK_SCREENSIZE = 0x0F
    SCREENSIZE_ANY = 0
    SCREENSIZE_SMALL = 1
    SCREENSIZE_NORMAL = 2
    SCREENSIZE_LARGE = 3
    SCREENSIZE_XLARGE = 4

    MASK_SCREENLONG = 0x30
    SHIFT_SCREENLONG = 4
    SCREENLONG_ANY = 0 << 4
    SCREENLONG_NO = 1 << 4
    SCREENLONG_YES = 2 << 4

    MASK_LAYOUTDIR = 0xC0
    SHIFT_LAYOUTDIR = 6
    LAYOUTDIR_ANY = 0 << 6
    LAYOUTDIR_LTR = 1 << 6
    LAYOUTDIR_RTL = 2 << 6

    MASK_UI_MODE_TYPE = 0x0F
    UI_MODE_TYPE_ANY = 0
    UI_MODE_TYPE_NORMAL = 1
    UI_MODE_TYPE_DESK = 2
    UI_MODE_TYPE_CAR = 3
    UI_MODE_TYPE_TELEVISION = 4
    UI_MODE_TYPE_APPLIANCE = 5
    UI_MODE_TYPE_WATCH = 6
    UI_MODE_TYPE_VR_HEADSET = 7

    MASK_UI_MODE_NIGHT = 0x30
    SHIFT_UI_MODE_NIGHT = 4
    UI_MODE_NIGHT_ANY = 0 << 4
    UI_MODE_NIGHT_NO = 1 << 4
    UI_MODE_NIGHT_YES = 2 << 4

    MASK_SCREENROUND = 0x03
    SCREENROUND_ANY = 0
    SCREENROUND_NO = 1
    SCREENROUND_YES = 2

    MASK_WIDE_COLOR_GAMUT = 0x03
    WIDE_COLOR_GAMUT_ANY = 0
    WIDE_COLOR_GAMUT_NO = 1
    WIDE_COLOR_GAMUT_YES = 2

    MASK_HDR = 0x0C
    SHIFT_COLOR_MODE_HDR = 2
    HDR_ANY = 0 << 2
    HDR_NO = 1 << 2
    HDR_YES = 2 << 2

    CONFIG_MCC = 0x0001
    CONFIG_MNC = 0x0002
    CONFIG_LOCALE = 0x0004
    CONFIG_TOUCHSCREEN = 0x0008
    CONFIG_KEYBOARD = 0x0010
    CONFIG_KEYBOARD_HIDDEN = 0x0020
    CONFIG_NAVIGATION = 0x0040
    CONFIG_ORIENTATION = 0x0080
    CONFIG_DENSITY = 0x0100
    CONFIG_SCREEN_SIZE = 0x0200
    CONFIG_VERSION = 0x0400
    CONFIG_SCREEN_LAYOUT = 0x0800
    CONFIG_UI_MODE = 0x1000
    CONFIG_SMALLEST_SCREEN_SIZE = 0x2000
    CONFIG_LAYOUTDIR = 0x4000
    CONFIG_SCREEN_ROUND = 0x8000
    CONFIG_COLOR_MODE = 0x10000
    CONFIG_GRAMMATICAL_GENDER = 0x20000

    _anonymous_ = (
        'imsi_u',
        'locale_u',
        'screenType_u',
        'input_container',
        'screenSize_u',
        'version_u',
        'screenConfig_u',
        'screenSizeDp_u',
        'screenConfig2_u',
    )

    _fields_ = [
        ('size', c_uint32),
        ('imsi_u', _ImsiUnion),
        ('locale_u', _LocaleUnion),
        ('screenType_u', _ScreenTypeUnion),
        ('input_container', _InputContainer),
        ('screenSize_u', _ScreenSizeUnion),
        ('version_u', _VersionUnion),
        ('screenConfig_u', _ScreenConfigUnion),
        ('screenSizeDp_u', _ScreenSizeDpUnion),
        ('localeScript', c_uint8 * 4),
        ('localeVariant', c_uint8 * 8),
        ('screenConfig2_u', _ScreenConfig2Union),
        ('localeScriptWasComputed', c_bool),
        ('localeNumberingSystem', c_uint8 * 8),
    ]


class ResTable_type(Structure):
    NO_ENTRY = 0xFFFFFFFF
    NO_ENTRY16 = 0xFFFF

    FLAG_SPARSE = 0x01
    FLAG_OFFSET16 = 0x02

    _fields_ = [
        ('header', ResChunk_header),
        ('id', c_uint8),
        ('flags', c_uint8),
        ('reserved', c_uint16),
        ('entryCount', c_uint32),
        ('entriesStart', c_uint32),
        ('config', ResTable_config),
    ]


class ResTable_sparseTypeEntry(Structure):
    _fields_ = [
        ('idx', c_uint16),
        ('offset', c_uint16),
    ]


class ResTable_entry:
    FLAG_COMPLEX = 0x0001
    FLAG_PUBLIC = 0x0002
    FLAG_WEAK = 0x0004
    FLAG_COMPACT = 0x0008

    class Full(Structure):
        _fields_ = [
            ('size', c_uint16),
            ('flags', c_uint16),
            ('key', c_uint32),
        ]

    class Compact(Structure):
        _fields_ = [
            ('key', c_uint16),
            ('flags', c_uint16),
            ('data', c_uint32),
        ]


class ResTable_map_entry(Structure):
    _fields_ = [
        ('size', c_uint16),
        ('flags', c_uint16),
        ('key', c_uint32),
        ('parent', c_uint32),
        ('count', c_uint32),
    ]


class Res_value(Structure):
    TYPE_NULL = 0x00
    TYPE_REFERENCE = 0x01
    TYPE_ATTRIBUTE = 0x02
    TYPE_STRING = 0x03
    TYPE_FLOAT = 0x04
    TYPE_DIMENSION = 0x05
    TYPE_FRACTION = 0x06
    TYPE_DYNAMIC_REFERENCE = 0x07
    TYPE_DYNAMIC_ATTRIBUTE = 0x08

    TYPE_FIRST_INT = 0x10
    TYPE_INT_DEC = 0x10
    TYPE_INT_HEX = 0x11
    TYPE_INT_BOOLEAN = 0x12

    TYPE_FIRST_COLOR_INT = 0x1C
    TYPE_INT_COLOR_ARGB8 = 0x1C
    TYPE_INT_COLOR_RGB8 = 0x1D
    TYPE_INT_COLOR_ARGB4 = 0x1E
    TYPE_INT_COLOR_RGB4 = 0x1F
    TYPE_LAST_COLOR_INT = 0x1F
    TYPE_LAST_INT = 0x1F

    COMPLEX_UNIT_SHIFT = 0
    COMPLEX_UNIT_MASK = 0xF

    COMPLEX_UNIT_PX = 0
    COMPLEX_UNIT_DIP = 1
    COMPLEX_UNIT_SP = 2
    COMPLEX_UNIT_PT = 3
    COMPLEX_UNIT_IN = 4
    COMPLEX_UNIT_MM = 5

    COMPLEX_UNIT_FRACTION = 0
    COMPLEX_UNIT_FRACTION_PARENT = 1

    COMPLEX_RADIX_SHIFT = 4
    COMPLEX_RADIX_MASK = 0x3
    COMPLEX_RADIX_23p0 = 0
    COMPLEX_RADIX_16p7 = 1
    COMPLEX_RADIX_8p15 = 2
    COMPLEX_RADIX_0p23 = 3

    COMPLEX_MANTISSA_SHIFT = 8
    COMPLEX_MANTISSA_MASK = 0xFFFFFF

    DATA_NULL_UNDEFINED = 0
    DATA_NULL_EMPTY = 1

    _fields_ = [
        ('size', c_uint16),
        ('res0', c_uint8),
        ('dataType', c_uint8),
        ('data', c_uint32),
    ]


def RES_MAKEINTERNAL(x: int) -> int:
    return 0x01000000 | x


class ResTable_map(Structure):
    ATTR_TYPE = RES_MAKEINTERNAL(0)
    ATTR_MIN = RES_MAKEINTERNAL(1)
    ATTR_MAX = RES_MAKEINTERNAL(2)
    ATTR_L10N = RES_MAKEINTERNAL(3)
    ATTR_OTHER = RES_MAKEINTERNAL(4)
    ATTR_ZERO = RES_MAKEINTERNAL(5)
    ATTR_ONE = RES_MAKEINTERNAL(6)
    ATTR_TWO = RES_MAKEINTERNAL(7)
    ATTR_FEW = RES_MAKEINTERNAL(8)
    ATTR_MANY = RES_MAKEINTERNAL(9)

    TYPE_ANY = 0x0000FFFF
    TYPE_REFERENCE = 1 << 0
    TYPE_STRING = 1 << 1
    TYPE_INTEGER = 1 << 2
    TYPE_BOOLEAN = 1 << 3
    TYPE_COLOR = 1 << 4
    TYPE_FLOAT = 1 << 5
    TYPE_DIMENSION = 1 << 6
    TYPE_FRACTION = 1 << 7
    TYPE_ENUM = 1 << 16
    TYPE_FLAGS = 1 << 17

    L10N_NOT_REQUIRED = 0
    L10N_SUGGESTED = 1

    _fields_ = [
        ('name', c_uint32),
        ('value', Res_value),
    ]


class ResStringPool_span(Structure):
    END = 0xFFFFFFFF

    _fields_ = [
        ('name', c_uint32),
        ('firstChar', c_uint32),
        ('lastChar', c_uint32),
    ]


class ResTable_typeSpec(Structure):
    SPEC_PUBLIC = 0x40000000
    SPEC_STAGED_API = 0x20000000

    _fields_ = [
        ('header', ResChunk_header),
        ('id', c_uint8),
        ('res0', c_uint8),
        ('typesCount', c_uint16),
        ('entryCount', c_uint32),
    ]


class ResXMLTree_header(Structure):
    _fields_ = [
        ('header', ResChunk_header),
    ]


class ResXMLTree_node(Structure):
    _fields_ = [
        ('header', ResChunk_header),
        ('lineNumber', c_uint32),
        ('comment', c_uint32),
    ]


class ResXMLTree_cdataExt(Structure):
    _fields_ = [
        ('data', c_uint32),
        ('typedData', Res_value),
    ]


class ResXMLTree_namespaceExt(Structure):
    _fields_ = [
        ('prefix', c_uint32),
        ('uri', c_uint32),
    ]


class ResXMLTree_endElementExt(Structure):
    _fields_ = [
        ('ns', c_uint32),
        ('name', c_uint32),
    ]


class ResXMLTree_attrExt(Structure):
    _fields_ = [
        ('ns', c_uint32),
        ('name', c_uint32),
        ('attributeStart', c_uint16),
        ('attributeSize', c_uint16),
        ('attributeCount', c_uint16),
        ('idIndex', c_uint16),
        ('classIndex', c_uint16),
        ('styleIndex', c_uint16),
    ]


class ResXMLTree_attribute(Structure):
    _fields_ = [
        ('ns', c_uint32),
        ('name', c_uint32),
        ('rawValue', c_uint32),
        ('typedValue', Res_value),
    ]

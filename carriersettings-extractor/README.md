# carriersettings-extractor

Android Open Source Project (AOSP) [includes](https://source.android.com/devices/tech/config/update) APN settings ([`apns-full-conf.xml`](https://android.googlesource.com/device/sample/+/master/etc/apns-full-conf.xml)) and [carrier settings](https://source.android.com/devices/tech/config/carrier) ([`carrier_config_*.xml`](https://android.googlesource.com/platform/packages/apps/CarrierConfig/+/master/assets) + [`vendor.xml`](https://android.googlesource.com/platform/packages/apps/CarrierConfig/+/refs/heads/master/res/xml/vendor.xml)) in human-readable XML format. However, Google Pixel device images instead include APN and carrier settings as binary protobuf files for use by the CarrierSettings system app.

This script converts the CarrierSettings protobuf files (e.g., `carrier_list.pb`, `others.pb`) to XML format compatible with AOSP. This may be helpful for Android-based systems that do not bundle CarrierSettings, but wish to support carriers that are not included in AOSP.

For a description of each APN and carrier setting, refer to the doc comments in [`Telephony.java`](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/master/core/java/android/provider/Telephony.java) and [`CarrierConfigManager.java`](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/master/telephony/java/android/telephony/CarrierConfigManager.java), respectively.

## Dependencies

 * curl - required, for android-prepare-vendor
 * e2fsprogs (debugfs) - required, for android-prepare-vendor
 * git - required, for android-prepare-vendor
 * protobuf-compiler (protoc) - optional, see below
 * python3-protobuf - required

## Usage

Download the [carrier ID database](https://source.android.com/devices/tech/config/carrierid) from AOSP.

    ./download_carrier_list.sh

Download a [Pixel factory image](https://developers.google.com/android/images) and extract the CarrierSettings protobuf files. This script will download android-prepare-vendor and copy the directory `CarrierSettings` containing the protobuf files.

    DEVICE=crosshatch BUILD=QQ3A.200605.001 ./download_factory_img.sh

Convert `CarrierSettings/*.pb` to `apns-full-conf.xml` and `vendor.xml`.

    ./carriersettings_extractor.py CarrierSettings

## Protobuf definitions

The definitions in [`carriersettings.proto`](carriersettings.proto) are useful for inspecting the CarrierSettings protobuf files.

    protoc --decode=CarrierList carriersettings.proto < CarrierSettings/carrier_list.pb
    protoc --decode=CarrierSettings carriersettings.proto < CarrierSettings/verizon_us.pb
    protoc --decode=MultiCarrierSettings carriersettings.proto < CarrierSettings/others.pb

To check schema or otherwise inspect the protobuf files without applying definitions, use the `--decode_raw` argument.

    protoc --decode_raw < CarrierSettings/carrier_list.pb
    protoc --decode_raw < CarrierSettings/verizon_us.pb
    protoc --decode_raw < CarrierSettings/others.pb

# carriersettings-extractor

Android Open Source Project (AOSP) [includes](https://source.android.com/devices/tech/config/update) APN settings ([`apns-full-conf.xml`](https://android.googlesource.com/device/sample/+/main/etc/apns-full-conf.xml)) and [carrier settings](https://source.android.com/devices/tech/config/carrier) ([`carrier_config_*.xml`](https://android.googlesource.com/platform/packages/apps/CarrierConfig/+/main/assets) + [`vendor.xml`](https://android.googlesource.com/platform/packages/apps/CarrierConfig/+/refs/heads/main/res/xml/vendor.xml)) in human-readable XML format. However, Google Pixel device images instead include APN and carrier settings as binary protobuf files for use by the CarrierSettings system app.

This script converts the CarrierSettings protobuf files (e.g., `carrier_list.pb`, `others.pb`) to XML format compatible with AOSP. This may be helpful for Android-based systems that do not bundle CarrierSettings, but wish to support carriers that are not included in AOSP.

For a description of each APN and carrier setting, refer to the doc comments in [`Telephony.java`](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/main/core/java/android/provider/Telephony.java) and [`CarrierConfigManager.java`](https://android.googlesource.com/platform/frameworks/base/+/refs/heads/main/telephony/java/android/telephony/CarrierConfigManager.java), respectively.

## Dependencies

 * protobuf-compiler (protoc) - optional, see below
 * python3-protobuf - required

## Usage

Download a [Pixel factory image](https://developers.google.com/android/images) and extract the CarrierSettings protobuf files.
Convert `CarrierSettings/*.pb` to `apns-full-conf.xml` and `vendor.xml`.

    ./carriersettings_extractor.py -i CarrierSettings -a apns-conf.xml -v vendor.xml

## Protobuf definitions

The definitions in [`carrier_list.proto`](carrier_list.proto) and [`carrier_settings.proto`](carrier_settings.proto) are useful for inspecting the CarrierSettings protobuf files.

    protoc --decode=com.google.carrier.CarrierList carrier_list.proto < CarrierSettings/carrier_list.pb
    protoc --decode=com.google.carrier.CarrierSettings carrier_settings.proto < CarrierSettings/verizon_us.pb
    protoc --decode=com.google.carrier.MultiCarrierSettings carrier_settings.proto < CarrierSettings/others.pb

To check schema or otherwise inspect the protobuf files without applying definitions, use the `--decode_raw` argument.

    protoc --decode_raw < CarrierSettings/carrier_list.pb
    protoc --decode_raw < CarrierSettings/verizon_us.pb
    protoc --decode_raw < CarrierSettings/others.pb

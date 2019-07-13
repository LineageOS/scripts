# config-fs-gen

```
usage: config-fs-gen.py [-h]
                        capability_header_path system_filesystem_config_path
                        vendor_group_path fs_config_paths
                        [fs_config_paths ...]

Convert /vendor/etc/group ×
/(system|vendor)/etc/(fs_config_dirs|fs_config_files) to config.fs

positional arguments:
  capability_header_path
                        path to {kernel}/include/uapi/linux/capability.h
  system_filesystem_config_path
                        path to {android}/system/core/libcutils/include/privat
                        e/android_filesystem_config.h
  vendor_group_path     path to {rom}/vendor/etc/group
  fs_config_paths       paths to
                        {rom}/(system|vendor)/etc/fs_config_(dirs|files)

optional arguments:
  -h, --help            show this help message and exit
```
```
  Example usage:
    $ ./config-fs-gen.py ~/lineage-16.0/kernel/oneplus/sm8150/include/uapi/linux/capability.h \
      ~/lineage-16.0/system/core/libcutils/include/private/android_filesystem_config.h \
      ~/lineage-16.0/out/target/product/guacamole/vendor/etc/group \
      ~/lineage-16.0/out/target/product/guacamole/{system,vendor}/etc/{fs_config_dirs,fs_config_files}
    [AID_VENDOR_QTI_DIAG]
    value:2901

    [AID_VENDOR_QDSS]
    value:2902

    [AID_VENDOR_RFS]
    value:2903

    [AID_VENDOR_RFS_SHARED]
    value:2904

    [AID_VENDOR_ADPL_ODL]
    value:2905

    [AID_VENDOR_QRTR]
    value:2906

    [bt_firmware/]
    mode: 0771
    user: AID_SYSTEM
    group: AID_SYSTEM
    caps: 0

    [dsp/]
    mode: 0771
    user: AID_MEDIA
    group: AID_MEDIA
    caps: 0

    [firmware/]
    mode: 0771
    user: AID_SYSTEM
    group: AID_SYSTEM
    caps: 0

    [firmware/image/*]
    mode: 0771
    user: AID_SYSTEM
    group: AID_SYSTEM
    caps: 0

    [persist/]
    mode: 0771
    user: AID_SYSTEM
    group: AID_SYSTEM
    caps: 0

    [vendor/bin/cnd]
    mode: 0755
    user: AID_SYSTEM
    group: AID_SYSTEM
    caps: NET_BIND_SERVICE NET_ADMIN BLOCK_SUSPEND

    [vendor/bin/hw/android.hardware.bluetooth@1.0-service-qti]
    mode: 0755
    user: AID_BLUETOOTH
    group: AID_BLUETOOTH
    caps: NET_ADMIN BLOCK_SUSPEND

    [vendor/bin/ims_rtp_daemon]
    mode: 0755
    user: AID_SYSTEM
    group: AID_RADIO
    caps: NET_BIND_SERVICE

    [vendor/bin/imsdatadaemon]
    mode: 0755
    user: AID_SYSTEM
    group: AID_SYSTEM
    caps: NET_BIND_SERVICE

    [vendor/bin/imsrcsd]
    mode: 0755
    user: AID_SYSTEM
    group: AID_RADIO
    caps: NET_BIND_SERVICE WAKE_ALARM BLOCK_SUSPEND

    [vendor/bin/loc_launcher]
    mode: 0755
    user: AID_GPS
    group: AID_GPS
    caps: SETGID SETUID

    [vendor/bin/pd-mapper]
    mode: 0755
    user: AID_SYSTEM
    group: AID_SYSTEM
    caps: NET_BIND_SERVICE

    [vendor/bin/pm-service]
    mode: 0755
    user: AID_SYSTEM
    group: AID_SYSTEM
    caps: NET_BIND_SERVICE

    [vendor/bin/sensors.qti]
    mode: 0755
    user: AID_SYSTEM
    group: AID_SYSTEM
    caps: NET_BIND_SERVICE

    [vendor/bin/slim_daemon]
    mode: 0755
    user: AID_GPS
    group: AID_GPS
    caps: NET_BIND_SERVICE

    [vendor/bin/wcnss_filter]
    mode: 0755
    user: AID_BLUETOOTH
    group: AID_BLUETOOTH
    caps: BLOCK_SUSPEND

    [vendor/bin/xtwifi-client]
    mode: 0755
    user: AID_GPS
    group: AID_GPS
    caps: NET_BIND_SERVICE WAKE_ALARM BLOCK_SUSPEND

    [vendor/firmware_mnt/image/*]
    mode: 0771
    user: AID_ROOT
    group: AID_SYSTEM
    caps: 0

    [vendor/lib/modules-aging/*]
    mode: 0644
    user: AID_ROOT
    group: AID_ROOT
    caps: 0
```

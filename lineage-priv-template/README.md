# lineage-priv-template

# Usage

1. Copy to $TOP/vendor/lineage-priv/keys
2. cd $TOP/vendor/lineage-priv/keys
3. ./keys.sh
4. Profit

# Testing

Included `check_keys.py` script checks whether all apk/apex/capex files in the build out are signed with keys within its directory. Be aware that some targets are **expected** to be signed with vendor key, for example `com.android.apex.cts.shim.v1_prebuilt`.

```
$ ./check_keys.py ~/lineage/out/target/product/lemonadep
/home/luk/lineage/out/target/product/lemonadep/obj/ETC/com.android.apex.cts.shim.v1_prebuilt_intermediates/com.android.apex.cts.shim.apex is signed with an unknown key!
```

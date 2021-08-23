# AIDL (service) generator

```
$ python3 -m aidl_gen -h
usage: aidl_gen [-h] -I INCLUDE fqname out_dir

positional arguments:
  fqname                Full qualifier of an AIDL interface (e.g.
                        android.hardware.light.ILights)
  out_dir               Folders where the service will be written on

optional arguments:
  -h, --help            show this help message and exit
  -I INCLUDE, --include INCLUDE
                        Folders to include that contains the AIDL interface
                        (note: use the folder where Android.bp resides, aka
                        the top AIDL folder), you can use multiple -I flags to
                        include multiple locations, but at least one is
                        required
```

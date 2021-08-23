# AIDL (service) generator

```
$ python3 -m aidl_gen -h
usage: aidl_gen [-h] fqname include_dir out_dir

positional arguments:
  fqname       Full qualifier of an AIDL interface (e.g.
               android.hardware.light.ILights)
  include_dir  Folders to include that contains the AIDL interface (note: use
               the folder where Android.bp resides)
  out_dir      Folders where the service will be written on

optional arguments:
  -h, --help   show this help message and exit
```

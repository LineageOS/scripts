# AIDL (service) generator

```
$ python -m aidl_gen -h
usage: aidl_gen [-h] -O OUT [-v VERSION] [-b {java,cpp,ndk,rust}] -I INCLUDE
                fqname

positional arguments:
  fqname                Full qualifier of an AIDL interface (e.g.
                        android.hardware.light.ILights)

options:
  -h, --help            show this help message and exit
  -O, --out OUT         Folders where the service will be written on
  -v, --version VERSION
                        Version of the AIDL interface (e.g. 1), if not
                        specified, the highest one available will be used
  -b, --backend {java,cpp,ndk,rust}
                        Backend to use for the generated service (default:
                        rust). Note: Java and C++ backends are for system
                        services, NDK and Rust are for vendor services
  -I, --include INCLUDE
                        Folders to include that contains the AIDL interface
                        (note: use the folder where Android.bp resides, aka
                        the top AIDL folder), you can use multiple -I flags to
                        include multiple locations, but at least one is
                        required

```

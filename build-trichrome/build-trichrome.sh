#!/bin/bash

set -e

chromium_version="80.0.3987.87"
clean=0
gsync=0
supported_archs=(arm arm64 x86 x64)

usage() {
    echo "Usage:"
    echo "  build_trichrome [ options ]"
    echo
    echo "  Options:"
    echo "    -a <arch> Build specified arch"
    echo "    -c Clean"
    echo "    -h Show this message"
    echo "    -r <release> Specify chromium release"
    echo "    -s Sync"
    echo
    echo "  Example:"
    echo "    build_trichrome -c -r $chromium_version"
    echo
    exit 1
}

build() {
    build_args=$args' target_cpu="'$1'"'
    gn gen "out/$1" --args="$build_args"
    ninja -C out/$1 trichrome_webview_apk trichrome_chrome_bundle trichrome_library_apk
}

while getopts ":a:chr:s" opt; do
    case $opt in
        a) for arch in ${supported_archs[@]}; do
               [ "$OPTARG" '==' "$arch" ] && build_arch="$OPTARG" || ((arch_try++))
           done
           if [ $arch_try -eq ${#supported_archs[@]} ]; then
               echo "Unsupported ARCH: $OPTARG"
               echo "Supported ARCHs: ${supported_archs[@]}"
               exit 1
           fi
           ;;
        c) clean=1 ;;
        h) usage ;;
        r) chromium_version="$OPTARG" ;;
        s) gsync=1 ;;
        :)
          echo "Option -$OPTARG requires an argument"
          echo
          usage
          ;;
        \?)
          echo "Invalid option:-$OPTARG"
          echo
          usage
          ;;
    esac
done
shift $((OPTIND-1))

# Add depot_tools to PATH
if [ ! -d depot_tools ]; then
    git clone https://chromium.googlesource.com/chromium/tools/depot_tools.git
fi
export PATH="$(pwd -P)/depot_tools:$PATH"

if [ ! -d src ]; then
    fetch android
    yes | gclient sync -D -R -r $chromium_version
fi

if [ $gsync -eq 1 ]; then
    find src -name index.lock -delete
    yes | gclient sync -D -R -r $chromium_version
fi
cd src

# Build args
args='target_os="android"'
args+=' blink_symbol_level=0'
args+=' enable_nacl=false'
args+=' enable_remoting=true'
args+=' enable_resource_whitelist_generation=false'
args+=' ffmpeg_branding="Chrome"'
args+=' is_chrome_branded=false'
args+=' is_component_build=false'
args+=' is_debug=false'
args+=' is_official_build=true'
args+=' proprietary_codecs=true'
args+=' symbol_level=0'
args+=' use_official_google_api_keys=false'
args+=' default_android_keystore_path = "//my-keystore.keystore"'
args+=' default_android_keystore_name = "my-key-alias"'
args+=' default_android_keystore_password = "my-password"'

# Setup environment
[ $clean -eq 1 ] && rm -rf out
. build/android/envsetup.sh

# Check target and build
if [ -n "$build_arch" ]; then
    build $build_arch
else
    build arm
    build arm64
    build x86
    build x64
fi

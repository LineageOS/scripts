#!/bin/bash

set -e

chromium_version="81.0.4044.117"
chromium_code="4044117"
clean=0
gsync=0
supported_archs=(arm arm64 x86 x64)

usage() {
    echo "Usage:"
    echo "  build_webview [ options ]"
    echo
    echo "  Options:"
    echo "    -a <arch> Build specified arch"
    echo "    -c Clean"
    echo "    -h Show this message"
    echo "    -r <release> Specify chromium release"
    echo "    -s Sync"
    echo
    echo "  Example:"
    echo "    build_webview -c -r $chromium_version:$chromium_code"
    echo
    exit 1
}

build() {
    build_args=$args' target_cpu="'$1'"'

    code=$chromium_code
    if [ $1 '==' "arm" ]; then
        code+=00
    elif [ $1 '==' "arm64" ]; then
        code+=50
    elif [ $1 '==' "x86" ]; then
        code+=10
    elif [ $1 '==' "x64" ]; then
        code+=60
    fi
    build_args+=' android_default_version_code="'$code'"'

    gn gen "out/$1" --args="$build_args"
    ninja -C out/$1 system_webview_apk
    if [ "$?" -eq 0 ]; then
        [ "$1" '==' "x64" ] && android_arch="x86_64" || android_arch=$1
        cp out/$1/apks/SystemWebView.apk ../android_external_chromium-webview/prebuilt/$android_arch/webview.apk
    fi
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
        r) version=(${OPTARG//:/ })
           chromium_version=$version[1]
           chromium_code=$version[2]
           ;;
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

# Download android_external_chromium-webview
if [ ! -d android_external_chromium-webview ]; then
    git clone https://github.com/LineageOS/android_external_chromium-webview.git --depth 1
fi

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
    yes | gclient sync -R -r $chromium_version
fi
cd src

# Replace webview icon
mkdir -p android_webview/nonembedded/java/res_icon/drawable-xxxhdpi
cp chrome/android/java/res_chromium/mipmap-mdpi/app_icon.png android_webview/nonembedded/java/res_icon/drawable-mdpi/icon_webview.png
cp chrome/android/java/res_chromium/mipmap-hdpi/app_icon.png android_webview/nonembedded/java/res_icon/drawable-hdpi/icon_webview.png
cp chrome/android/java/res_chromium/mipmap-xhdpi/app_icon.png android_webview/nonembedded/java/res_icon/drawable-xhdpi/icon_webview.png
cp chrome/android/java/res_chromium/mipmap-xxhdpi/app_icon.png android_webview/nonembedded/java/res_icon/drawable-xxhdpi/icon_webview.png
cp chrome/android/java/res_chromium/mipmap-xxxhdpi/app_icon.png android_webview/nonembedded/java/res_icon/drawable-xxxhdpi/icon_webview.png

# Apply our patches
if [ $gsync -eq 1 ]; then
    git am ../android_external_chromium-webview/patches/*
fi

# Build args
args='target_os="android"'
args+=' is_debug=false'
args+=' is_official_build=true'
args+=' is_chrome_branded=false'
args+=' use_official_google_api_keys=false'
args+=' ffmpeg_branding="Chrome"'
args+=' proprietary_codecs=true'
args+=' enable_resource_whitelist_generation=false'
args+=' enable_remoting=true'
args+=' is_component_build=false'
args+=' symbol_level=0'
args+=' enable_nacl=false'
args+=' blink_symbol_level = 0'
args+=' android_default_version_name="'$chromium_version'"'

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

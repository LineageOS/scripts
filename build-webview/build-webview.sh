#!/bin/bash

# SPDX-FileCopyrightText: 2019-2023 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0

set -e

chromium_version="142.0.7444.48"
chromium_code="7444048"
clean=0
gsync=0
supported_archs=(arm arm64 x86 x64)

lineage_github=https://github.com/LineageOS
lineage_gitlab=https://gitlab.com/LineageOS/android
webview_proj_base=android_external_chromium-webview

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

clone_proj() {
    depth=""
    if [ "$#" -eq 3 ]; then
        depth="--depth $3"
    fi

    if [ ! -d "$2" ]; then
        git clone $1 $2 $depth
    fi
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
        case $1 in
            x64)
                android_arch="x86_64"
                lineage_git=$lineage_gitlab
                ;;
            *)
                android_arch=$1
                lineage_git=$lineage_github
                ;;
        esac

        clone_proj ${lineage_git}/${webview_proj_base}_prebuilt_${android_arch}.git \
            ../${webview_proj_base}/prebuilt/${android_arch} 1

        cp out/$1/apks/SystemWebView.apk ../$webview_proj_base/prebuilt/$android_arch/webview.apk
    fi
}

while getopts ":a:chr:s" opt; do
    case $opt in
        a) for arch in ${supported_archs[@]}; do
               [ "$OPTARG" '==' "$arch" ] && build_arch="$OPTARG"
           done
           if [ -z "$build_arch" ]; then
               echo "Unsupported ARCH: $OPTARG"
               echo "Supported ARCHs: ${supported_archs[@]}"
               exit 1
           fi
           ;;
        c) clean=1 ;;
        h) usage ;;
        r) version=(${OPTARG//:/ })
           chromium_version=${version[0]}
           chromium_code=${version[1]}
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

# Download webview patches
clone_proj ${lineage_github}/${webview_proj_base}_patches.git \
    ${webview_proj_base}/patches

# Add depot_tools to PATH
if [ ! -d depot_tools ]; then
    git clone https://chromium.googlesource.com/chromium/tools/depot_tools.git
fi
export PATH="$(pwd -P)/depot_tools:$PATH"

if [ ! -d src ]; then
    fetch android
    yes | gclient sync -D -R -r $chromium_version
fi

# Apply our patches
if [ $gsync -eq 1 ]; then
    ( cd src
      git am ../android_external_chromium-webview/patches/*.patch
    )
fi

if [ $gsync -eq 1 ]; then
    find src -name index.lock -delete
    yes | gclient sync -R -r $chromium_version
fi
cd src

# Replace webview icon
mkdir -p android_webview/nonembedded/java/res_icon/drawable-xxxhdpi
cp chrome/android/java/res_chromium_base/mipmap-mdpi/app_icon.png android_webview/nonembedded/java/res_icon/drawable-mdpi/icon_webview.png
cp chrome/android/java/res_chromium_base/mipmap-hdpi/app_icon.png android_webview/nonembedded/java/res_icon/drawable-hdpi/icon_webview.png
cp chrome/android/java/res_chromium_base/mipmap-xhdpi/app_icon.png android_webview/nonembedded/java/res_icon/drawable-xhdpi/icon_webview.png
cp chrome/android/java/res_chromium_base/mipmap-xxhdpi/app_icon.png android_webview/nonembedded/java/res_icon/drawable-xxhdpi/icon_webview.png
cp chrome/android/java/res_chromium_base/mipmap-xxxhdpi/app_icon.png android_webview/nonembedded/java/res_icon/drawable-xxxhdpi/icon_webview.png

# Build args
args='target_os="android"'
args+=' is_debug=false'
args+=' is_official_build=true'
args+=' is_chrome_branded=false'
args+=' use_official_google_api_keys=false'
args+=' ffmpeg_branding="Chrome"'
args+=' proprietary_codecs=true'
args+=' enable_resource_allowlist_generation=false'
args+=' enable_remoting=false'
args+=' is_component_build=false'
args+=' symbol_level=0'
args+=' enable_nacl=false'
args+=' blink_symbol_level=0'
args+=' webview_devui_show_icon=false'
args+=' dfmify_dev_ui=false'
args+=' disable_fieldtrial_testing_config=true'
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

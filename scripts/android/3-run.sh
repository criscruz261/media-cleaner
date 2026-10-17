#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
if [[ "${1:-}" == --help || "${1:-}" == -h ]]; then
    echo 'Usage: ./scripts/android/3-run.sh DEVICE_SERIAL'
    echo 'Install and launch the built debug APK on a connected device or running emulator.'
    echo 'Find serials with: .tools/android/sdk/platform-tools/adb devices'
    echo 'Enable USB debugging and authorize this computer for a physical device.'
    exit 0
fi
if [[ $# -ne 1 ]]; then
    echo 'Specify one device serial. See ./scripts/android/3-run.sh --help.' >&2
    exit 1
fi
sdk_dir="${ANDROID_HOME:-$project_dir/.tools/android/sdk}"
adb_bin="$sdk_dir/platform-tools/adb"
apk="$project_dir/apps/android/app/build/outputs/apk/debug/app-debug.apk"
[[ -x "$adb_bin" ]] || { echo 'Android platform-tools missing; run 1-setup.sh or set ANDROID_HOME.' >&2; exit 1; }
[[ -f "$apk" ]] || { echo 'Run ./scripts/android/2-build.sh first.' >&2; exit 1; }
"$adb_bin" -s "$1" get-state
"$adb_bin" -s "$1" install -r "$apk"
exec "$adb_bin" -s "$1" shell am start -W -n com.photofold.mediacleaner/.MainActivity

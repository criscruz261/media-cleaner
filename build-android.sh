#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo 'Usage: ./build-android.sh [Gradle options, e.g. --offline]'
    echo 'Runs matching tests, builds the debug APK, and runs Android lint.'
    echo 'Run ./setup-android.sh first, or configure JAVA_HOME and ANDROID_HOME.'
    exit 0
fi
"$project_dir/apps/android/scripts/build.sh" "$@"
mkdir -p "$project_dir/.tools/dist"
cp "$project_dir/apps/android/app/build/outputs/apk/debug/app-debug.apk" "$project_dir/.tools/dist/media-cleaner-android-debug.apk"
cd "$project_dir/.tools/dist"
shasum -a 256 media-cleaner-android-debug.apk > media-cleaner-android-debug.apk.sha256
printf '\nAPK ready: %s\n' "$project_dir/.tools/dist/media-cleaner-android-debug.apk"

#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
if [[ "${1:-}" == --help || "${1:-}" == -h ]]; then
    echo 'Usage: ./scripts/android/4-create-deploy-package.sh [Gradle options, e.g. --offline]'
    echo 'Build, verify, and copy the debug APK and checksum to deployment-package/android/.'
    exit 0
fi
"$project_dir/scripts/android/2-build.sh" "$@"
export JAVA_HOME="${JAVA_HOME:-$project_dir/.tools/android/jdk/Contents/Home}"
sdk_dir="${ANDROID_HOME:-$project_dir/.tools/android/sdk}"
apk="$project_dir/apps/android/app/build/outputs/apk/debug/app-debug.apk"
"$sdk_dir/build-tools/35.0.0/apksigner" verify --verbose "$apk"
output="$project_dir/deployment-package/android"
mkdir -p "$output"
staging="$(mktemp -d "$output/.package-XXXXXXXX")"
trap 'rm -rf -- "$staging"' EXIT
cp "$apk" "$staging/media-cleaner-android-debug.apk"
cp "$project_dir/scripts/android/README-deployment.txt" "$staging/README.txt"
(
    cd "$staging"
    shasum -a 256 media-cleaner-android-debug.apk > media-cleaner-android-debug.apk.sha256
    shasum -a 256 -c media-cleaner-android-debug.apk.sha256
)
for name in media-cleaner-android-debug.apk media-cleaner-android-debug.apk.sha256 README.txt; do
    mv -f "$staging/$name" "$output/$name"
done
printf 'Android deployment package ready: %s\n' "$output"

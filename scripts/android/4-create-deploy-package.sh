#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
if [[ "${1:-}" == --help || "${1:-}" == -h ]]; then
    echo 'Usage: ./scripts/android/4-create-deploy-package.sh [Gradle options, e.g. --offline]'
    echo 'Build and verify the timestamped debug APK and checksum in deployment-package/android/.'
    exit 0
fi
version="$(date +%y%m%d%H%M)"
name="MediaCleaner-$version-android-debug"
"$project_dir/scripts/android/2-build.sh" "$@"
export JAVA_HOME="${JAVA_HOME:-$project_dir/.tools/android/jdk/Contents/Home}"
sdk_dir="${ANDROID_HOME:-$project_dir/.tools/android/sdk}"
apk="$project_dir/apps/android/app/build/outputs/apk/debug/app-debug.apk"
"$sdk_dir/build-tools/35.0.0/apksigner" verify --verbose "$apk"
output="$project_dir/deployment-package/android"
mkdir -p "$output"
staging="$(mktemp -d "$output/.package-XXXXXXXX")"
trap 'rm -rf -- "$staging"' EXIT
cp "$apk" "$staging/${name}.apk"
sed "s/MediaCleaner-android-debug.apk/${name}.apk/g" "$project_dir/scripts/android/README-deployment.txt" > "$staging/README.txt"
(
    cd "$staging"
    shasum -a 256 "${name}.apk" > "${name}.apk.sha256"
    shasum -a 256 -c "${name}.apk.sha256"
)
for file in "${name}.apk" "${name}.apk.sha256" README.txt; do
    mv -f "$staging/$file" "$output/$file"
done
printf 'Android APK ready: %s\n' "$output/$name.apk"

#!/usr/bin/env bash
# Starts only the repository's synthetic-test AVD; never targets a physical phone.
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)"
export JAVA_HOME="${JAVA_HOME:-$project_dir/.tools/android/jdk/Contents/Home}"
export ANDROID_HOME="${ANDROID_HOME:-$project_dir/.tools/android/sdk}"
export ANDROID_USER_HOME="$project_dir/.tools/android/user"
export ANDROID_AVD_HOME="$ANDROID_USER_HOME/avd"
export PATH="$JAVA_HOME/bin:$ANDROID_HOME/platform-tools:$PATH"
emulator_display=(-no-window)
if [[ "${1:-}" == "--window" ]]; then
    emulator_display=()
    shift
fi
if [[ ! -x "$ANDROID_HOME/emulator/emulator" ]] || [[ ! -d "$ANDROID_HOME/system-images/android-35/google_apis/arm64-v8a" ]]; then
    echo 'Emulator components missing. Run ./scripts/android/1-setup.sh --emulator first.' >&2
    exit 1
fi
mkdir -p "$ANDROID_AVD_HOME"
if [ ! -f "$ANDROID_AVD_HOME/media-cleaner-test.ini" ]; then
    "$ANDROID_HOME/cmdline-tools/latest/bin/avdmanager" create avd --name media-cleaner-test --package 'system-images;android-35;google_apis;arm64-v8a' --device pixel_6 <<'ANSWER'
no
ANSWER
fi
exec "$ANDROID_HOME/emulator/emulator" -avd media-cleaner-test -port 5554 "${emulator_display[@]}" -no-audio -no-snapshot -no-boot-anim -gpu swiftshader_indirect -memory 2048 -cores 2 -camera-back none -camera-front none "$@"

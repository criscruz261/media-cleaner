#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)"
export JAVA_HOME="${JAVA_HOME:-$project_dir/.tools/android/jdk/Contents/Home}"
export ANDROID_HOME="${ANDROID_HOME:-$project_dir/.tools/android/sdk}"
export ANDROID_USER_HOME="${ANDROID_USER_HOME:-$project_dir/.tools/android/user}"
export GRADLE_USER_HOME="${GRADLE_USER_HOME:-$project_dir/.tools/android/gradle-cache}"
export PATH="$JAVA_HOME/bin:$ANDROID_HOME/platform-tools:$PATH"
if [ ! -x "$JAVA_HOME/bin/java" ] || [ ! -d "$ANDROID_HOME/platforms" ]; then
    echo 'Install JDK 21 and Android SDK platform 35, or run apps/android/scripts/setup-tools.py after reviewing the SDK license.' >&2
    exit 1
fi
cd "$project_dir/apps/android"
exec ./gradlew --no-daemon :matching:test :app:assembleDebug :app:lintDebug "$@"

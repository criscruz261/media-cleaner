#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
if [[ "${1:-}" == --help || "${1:-}" == -h ]]; then
    echo 'Usage: ./scripts/android/2-build.sh [Gradle options, e.g. --offline]'
    echo 'Run matching tests, compile the debug APK, and run Android lint.'
    exit 0
fi
exec "$project_dir/build-android.sh" "$@"

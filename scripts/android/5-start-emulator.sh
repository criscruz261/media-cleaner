#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
if [[ "${1:-}" == --help || "${1:-}" == -h ]]; then
    echo 'Usage: ./scripts/android/5-start-emulator.sh [emulator options]'
    echo 'Open the local test emulator window as emulator-5554. Keep this terminal running.'
    echo 'Once it boots, run ./scripts/android/3-run.sh emulator-5554 in another terminal.'
    exit 0
fi
printf 'Starting emulator-5554. Wait for the Android home screen before installing the app.\n'
exec "$project_dir/apps/android/scripts/emulator.sh" --window "$@"

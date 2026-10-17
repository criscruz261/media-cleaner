#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
if [[ "${1:-}" == --help || "${1:-}" == -h ]]; then
    echo 'Usage: ./scripts/android/1-setup.sh [--accept-licenses] [--emulator]'
    echo 'Install local Android tools on macOS Apple Silicon. SDK licenses prompt by default.'
    exit 0
fi
# Honor both the existing Android override and the desktop Python override.
if [[ -z "${PYTHON:-}" ]]; then
    source "$project_dir/scripts/macOS/python.sh"
    export PYTHON="$(find_macos_python)"
fi
exec "$project_dir/setup-android.sh" "$@"

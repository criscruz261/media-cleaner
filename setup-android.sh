#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo 'Usage: ./setup-android.sh [--accept-licenses] [--emulator]'
    echo 'Installs local JDK 21 and Android SDK 35 on macOS Apple Silicon.'
    echo 'Requires Python 3.12+ and curl. Downloads are saved in ignored .tools/android.'
    echo 'SDK licenses are interactive unless --accept-licenses is supplied.'
    exit 0
fi
python_bin="${PYTHON:-}"
if [[ -z "$python_bin" ]]; then
    for candidate in python3.14 python3.13 python3.12 python3 "$project_dir/.venv-phase1/bin/python"; do
        if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 12))' 2>/dev/null; then
            python_bin="$candidate"
            break
        fi
    done
fi
if [[ -z "$python_bin" ]] || ! "$python_bin" -c 'import sys; sys.exit(sys.version_info < (3, 12))'; then
    echo 'Python 3.12+ is required. Install it, or set PYTHON to its executable path.' >&2
    exit 1
fi
command -v curl >/dev/null 2>&1 || { echo 'curl is required.' >&2; exit 1; }
exec "$python_bin" "$project_dir/apps/android/scripts/setup-tools.py" "$@"

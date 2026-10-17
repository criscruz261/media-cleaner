#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
if [ "$(uname -s)" != Darwin ]; then
    echo "Run this script on macOS." >&2
    exit 1
fi
cd "$project_dir"
if [ ! -x "$project_dir/.venv-phase1/bin/python" ]; then
    echo "Run ./scripts/macOS/1-setup.sh first." >&2
    exit 1
fi
"$project_dir/scripts/macOS/2-build.sh"
export PYINSTALLER_CONFIG_DIR="$project_dir/.tools/pyinstaller-cache"
exec "$project_dir/.venv-phase1/bin/python" "$project_dir/apps/desktop/packaging/macos/build_package.py"

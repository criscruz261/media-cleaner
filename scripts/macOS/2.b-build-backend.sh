#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
if [ "$(uname -s)" != Darwin ]; then
    echo "Run this script on macOS." >&2
    exit 1
fi
cd "$project_dir"
python_bin="$project_dir/.venv-phase1/bin/python"
if [ ! -x "$python_bin" ]; then
    echo "Run ./scripts/macOS/1-setup.sh first." >&2
    exit 1
fi
"$python_bin" -m pip wheel --no-deps --no-build-isolation --wheel-dir "$project_dir/apps/desktop/backend/dist" "$project_dir/apps/desktop/backend"

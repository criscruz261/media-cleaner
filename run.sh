#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
python_bin="$project_dir/.venv-phase1/bin/python"
if [ ! -x "$python_bin" ]; then
    echo "Run scripts/setup.sh first (Python 3.12+ and Node 22.12+ required)." >&2
    exit 1
fi
if [ ! -f "$project_dir/frontend/dist/index.html" ]; then
    echo "Build the frontend first: cd frontend && npm ci && npm run build" >&2
    exit 1
fi
cd "$project_dir/backend"
exec "$python_bin" -m app "$@"

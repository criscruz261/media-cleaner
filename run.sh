#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
    echo "PhotoFold requires Python 3.10 or newer. Install Python and try again." >&2
    exit 1
fi

if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
    echo "PhotoFold requires Python 3.10 or newer." >&2
    exit 1
fi

exec python3 "$project_dir/app.py" "$@"

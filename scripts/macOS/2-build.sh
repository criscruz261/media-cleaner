#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
if [ "$(uname -s)" != Darwin ]; then
    echo "Run this script on macOS." >&2
    exit 1
fi
cd "$project_dir"
"$project_dir/scripts/macOS/2.a-build-frontend.sh"
"$project_dir/scripts/macOS/2.b-build-backend.sh"

#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
if [ "$(uname -s)" != Darwin ]; then
    echo "Run this script on macOS." >&2
    exit 1
fi
cd "$project_dir"
source "$project_dir/scripts/toolchain.sh"
source "$project_dir/scripts/macOS/python.sh"
python_bin="$(find_macos_python)"
printf 'Using Python: %s\n' "$python_bin"
node -e 'const [major, minor] = process.versions.node.split(".").map(Number); if (major < 22 || (major === 22 && minor < 12)) throw Error("Node 22.12+ is required")'
"$python_bin" -m venv .venv-phase1
.venv-phase1/bin/python -m pip install -r apps/desktop/backend/requirements-dev.lock
.venv-phase1/bin/python -m pip install --no-deps -e apps/desktop/backend
.venv-phase1/bin/python -m pip install 'pyinstaller==6.22.3' hatchling
.venv-phase1/bin/python apps/desktop/scripts/install-media-tools.py
npm ci --prefix apps/desktop/frontend
printf 'Dependencies installed. Run ./scripts/macOS/2-build.sh next.\n'

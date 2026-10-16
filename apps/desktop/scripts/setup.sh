#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)"
source "$project_dir/scripts/toolchain.sh"
cd "$project_dir"
python_bin="${PYTHON_BIN:-python3}"
if ! "$python_bin" -c 'import sys; assert sys.version_info >= (3, 12)'; then
    echo "Python 3.12+ is required. Set PYTHON_BIN to its executable path." >&2
    exit 1
fi
command -v npm >/dev/null || { echo 'Node 22.12+ and npm are required.' >&2; exit 1; }
"$python_bin" -m venv .venv-phase1
.venv-phase1/bin/python -m pip install -r apps/desktop/backend/requirements-dev.lock
.venv-phase1/bin/python -m pip install --no-deps -e apps/desktop/backend
.venv-phase1/bin/python apps/desktop/scripts/install-media-tools.py
npm ci --prefix apps/desktop/frontend
npm run build --prefix apps/desktop/frontend
printf 'Setup complete. Run ./run.sh and open the printed launch link.\n'

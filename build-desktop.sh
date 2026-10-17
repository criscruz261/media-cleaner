#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo 'Usage: ./build-desktop.sh'
    echo 'Builds the production desktop frontend for ./run.sh (not an installer).'
    echo 'Run ./scripts/setup.sh once on a newly cloned repository.'
    exit 0
fi
if [[ $# -ne 0 ]]; then
    echo 'Usage: ./build-desktop.sh' >&2
    exit 1
fi
source "$project_dir/scripts/toolchain.sh"
command -v npm >/dev/null || { echo 'Node 22.12+ and npm are required.' >&2; exit 1; }
if [[ ! -x "$project_dir/.venv-phase1/bin/python" ]]; then
    echo 'Run ./scripts/setup.sh first to prepare the desktop environment.' >&2
    exit 1
fi
# Refresh dependencies from the lockfile so dependency changes are included.
npm ci --prefer-offline --no-audit --no-fund --prefix "$project_dir/apps/desktop/frontend"
npm run build --prefix "$project_dir/apps/desktop/frontend"
printf '\nDesktop build ready. Start the app with ./run.sh\n'

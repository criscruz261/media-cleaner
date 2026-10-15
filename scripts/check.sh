#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
source "$project_dir/scripts/toolchain.sh"
cd "$project_dir/backend"
../.venv-phase1/bin/python -m ruff check app tests
../.venv-phase1/bin/python -m pytest
cd "$project_dir/frontend"
npm test
npm run build

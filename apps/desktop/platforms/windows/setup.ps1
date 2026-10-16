$ErrorActionPreference = 'Stop'
Set-Location (Resolve-Path (Join-Path $PSScriptRoot "../../../..")).Path
if ($env:PYTHON_BIN) { $Python = $env:PYTHON_BIN } else { $Python = 'python' }
& $Python -c 'import sys; assert sys.version_info >= (3,12)'
if ($LASTEXITCODE -ne 0) { throw 'Python 3.12+ required. Set PYTHON_BIN to its path.' }
& $Python -m venv .venv-phase1
& .\.venv-phase1\Scripts\python.exe -m pip install -r apps/desktop/backend/requirements-dev.lock
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
& .\.venv-phase1\Scripts\python.exe -m pip install --no-deps -e apps/desktop/backend
if ($LASTEXITCODE -ne 0) { throw 'Backend installation failed' }
& .\.venv-phase1\Scripts\python.exe apps/desktop/scripts/install-media-tools.py
if ($LASTEXITCODE -ne 0) { throw 'Media tool installation failed' }
npm ci --prefix apps/desktop/frontend
if ($LASTEXITCODE -ne 0) { throw 'Frontend installation failed' }
npm run build --prefix apps/desktop/frontend
if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed' }
Write-Host 'Setup complete. Run ./scripts/run.ps1'

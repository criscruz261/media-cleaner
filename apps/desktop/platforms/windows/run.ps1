$ErrorActionPreference = 'Stop'
$Project = (Resolve-Path (Join-Path $PSScriptRoot "../../../..")).Path
if (!(Test-Path "$Project/apps/desktop/frontend/dist/index.html")) { throw 'Run scripts/setup.ps1 first' }
Set-Location "$Project/apps/desktop/backend"
& "$Project/.venv-phase1/Scripts/python.exe" -m app @args
exit $LASTEXITCODE

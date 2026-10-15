$ErrorActionPreference = 'Stop'
$Project = Split-Path $PSScriptRoot -Parent
if (!(Test-Path "$Project/frontend/dist/index.html")) { throw 'Run scripts/setup.ps1 first' }
Set-Location "$Project/backend"
& "$Project/.venv-phase1/Scripts/python.exe" -m app @args
exit $LASTEXITCODE

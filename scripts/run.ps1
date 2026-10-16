$ErrorActionPreference = 'Stop'
$Project = Split-Path $PSScriptRoot -Parent
& "$Project/apps/desktop/platforms/windows/run.ps1" @args
exit $LASTEXITCODE

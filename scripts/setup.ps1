$ErrorActionPreference = 'Stop'
$Project = Split-Path $PSScriptRoot -Parent
& "$Project/apps/desktop/platforms/windows/setup.ps1" @args
exit $LASTEXITCODE

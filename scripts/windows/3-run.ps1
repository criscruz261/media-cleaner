$ErrorActionPreference = 'Stop'
$Project = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
& "$Project/apps/desktop/platforms/windows/run.ps1" @args
exit $LASTEXITCODE

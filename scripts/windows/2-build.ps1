$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $ProjectRoot
if ($env:OS -ne 'Windows_NT') { throw 'Build the Windows application on Windows.' }

& "$PSScriptRoot\2.a-build-frontend.ps1"
if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
& "$PSScriptRoot\2.b-build-backend.ps1"
if ($LASTEXITCODE -ne 0) { throw 'Backend wheel build failed.' }

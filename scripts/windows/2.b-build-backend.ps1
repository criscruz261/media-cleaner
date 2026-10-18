$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $ProjectRoot
if ($env:OS -ne 'Windows_NT') { throw 'Build the Windows backend on Windows.' }

$Python = Join-Path $ProjectRoot '.venv-phase1\Scripts\python.exe'
if (!(Test-Path -LiteralPath $Python)) { throw 'Run .\scripts\windows\1-setup.ps1 first.' }
$Backend = Join-Path $ProjectRoot 'apps\desktop\backend'
$WheelDirectory = Join-Path $Backend 'dist'
New-Item -ItemType Directory -Path $WheelDirectory -Force | Out-Null
& $Python -m pip wheel --no-deps --no-build-isolation --wheel-dir $WheelDirectory $Backend
if ($LASTEXITCODE -ne 0) { throw 'Backend wheel build failed.' }

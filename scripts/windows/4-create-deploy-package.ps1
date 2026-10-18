[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $ProjectRoot
if ($env:OS -ne 'Windows_NT') { throw 'Build the Windows package on Windows.' }
$Python = Join-Path $ProjectRoot '.venv-phase1\Scripts\python.exe'
if (!(Test-Path -LiteralPath $Python)) { throw 'Run .\scripts\windows\1-setup.ps1 first.' }

# Setup also finds/installs Node.js and rebuilds the frontend from the lockfile.
& "$PSScriptRoot\1-setup.ps1"
if ($LASTEXITCODE -ne 0) { throw 'Desktop setup failed.' }
& "$PSScriptRoot\2-build.ps1"
if ($LASTEXITCODE -ne 0) { throw 'Desktop build failed.' }
& $Python -m pip install 'pyinstaller==6.22.3'
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller installation failed.' }
& $Python "$ProjectRoot\apps\desktop\packaging\windows\build_package.py"
if ($LASTEXITCODE -ne 0) { throw 'Windows packaging or smoke test failed. See output above.' }
Write-Host 'Ready: deployment-package\windows\MediaCleaner.exe'
Write-Host 'Copy the ENTIRE deployment-package\windows folder to the other Windows PC.'

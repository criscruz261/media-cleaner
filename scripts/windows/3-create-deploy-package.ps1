[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
& "$PSScriptRoot\4-create-deploy-package.ps1"
exit $LASTEXITCODE

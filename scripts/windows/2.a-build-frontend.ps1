$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $ProjectRoot
if ($env:OS -ne 'Windows_NT') { throw 'Build the Windows frontend on Windows.' }

$NodeCandidates = @(Get-ChildItem "$ProjectRoot\.tools\node\node-v*-win-*\node.exe" -ErrorAction SilentlyContinue |
    Sort-Object FullName -Descending | ForEach-Object { $_.FullName })
$NodeCandidates += @(Get-Command node.exe -All -ErrorAction SilentlyContinue |
    ForEach-Object { $_.Source })
$Node = $null
foreach ($Candidate in ($NodeCandidates | Select-Object -Unique)) {
    if (!(Test-Path -LiteralPath $Candidate)) { continue }
    $VersionOutput = & $Candidate --version
    $VersionMatch = [regex]::Match(($VersionOutput -join "`n").Trim(), '^v(\d+\.\d+\.\d+)$')
    if ($LASTEXITCODE -eq 0 -and $VersionMatch.Success -and
        ([version]$VersionMatch.Groups[1].Value -ge [version]'22.12.0')) {
        $Node = $Candidate
        break
    }
}
if (!$Node) { throw 'Node.js 22.12+ was not found. Run .\scripts\windows\1-setup.ps1 first.' }

$NpmRunner = Join-Path $ProjectRoot 'apps\desktop\platforms\windows\run-npm.cjs'
& $Node $NpmRunner run build --prefix apps/desktop/frontend
if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }

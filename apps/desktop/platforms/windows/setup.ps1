$ErrorActionPreference = 'Stop'
Set-Location (Resolve-Path (Join-Path $PSScriptRoot "../../../..")).Path
$ProjectRoot = (Get-Location).Path

function Update-SetupPath {
    # Installers update the registry, not the environment of this terminal.
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
        [Environment]::GetEnvironmentVariable('Path', 'User') + ';' + $env:Path
}

function Install-Prerequisite([string]$Package) {
    if (!(Get-Command winget.exe -ErrorAction SilentlyContinue)) {
        throw "Cannot install $Package automatically: winget is missing. Install Microsoft's App Installer, then rerun setup."
    }
    Write-Host "Installing $Package using winget..."
    & winget.exe install --id $Package --exact --source winget --accept-package-agreements --accept-source-agreements --disable-interactivity
    $InstallExitCode = $LASTEXITCODE
    Update-SetupPath
    # Winget may already know this package even when this terminal cannot find it.
    # The caller must still validate the actual executable and required version.
    if ($InstallExitCode -eq -1978335189) {
        Write-Host "$Package is already registered with winget; checking the installed runtime."
    } elseif ($InstallExitCode -ne 0) {
        throw "Installation of $Package failed (exit $InstallExitCode). Resolve the installer error and rerun setup."
    }
}

function Find-Python {
    $Candidates = @()
    if ($env:PYTHON_BIN) {
        $Candidates = @($env:PYTHON_BIN)
    } else {
        # The launcher can find Python even when python.exe is not on PATH.
        if (Get-Command py.exe -ErrorAction SilentlyContinue) {
            try {
                $Located = & py.exe -3 -c 'import sys; print(sys.executable)' 2>$null
                if ($LASTEXITCODE -eq 0) { $Candidates += $Located }
            } catch { } # A launcher may be installed without a Python runtime.
        }
        $Candidates += @(Get-Command python.exe -All -ErrorAction SilentlyContinue |
            Where-Object { $_.Source -notlike '*\Microsoft\WindowsApps\*' } |
            ForEach-Object { $_.Source })
        $Candidates += @(Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python*\python.exe", "$env:ProgramFiles\Python*\python.exe" -ErrorAction SilentlyContinue |
            Sort-Object FullName -Descending | ForEach-Object { $_.FullName })
    }
    foreach ($Candidate in $Candidates) {
        if (!(Test-Path -LiteralPath $Candidate)) { continue }
        try {
            $Executable = & $Candidate -c 'import sys; assert sys.version_info >= (3,12); print(sys.executable)' 2>$null
            if ($LASTEXITCODE -eq 0) { return $Executable }
        } catch { } # Continue past older or broken Python installations.
    }
}

function Find-Node {
    $Candidates = @(Get-ChildItem "$ProjectRoot\.tools\node\node-v*-win-*\node.exe" -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending | ForEach-Object { $_.FullName })
    $Candidates += @(Get-Command node.exe -All -ErrorAction SilentlyContinue |
        ForEach-Object { $_.Source })
    # MSI installations can exist without a usable PATH entry in this session.
    $Candidates += @(
        "$env:ProgramFiles\nodejs\node.exe",
        "${env:ProgramFiles(x86)}\nodejs\node.exe",
        "$env:LOCALAPPDATA\Programs\nodejs\node.exe",
        "$env:LOCALAPPDATA\nodejs\node.exe"
    )
    foreach ($Candidate in ($Candidates | Select-Object -Unique)) {
        if (!(Test-Path -LiteralPath $Candidate)) { continue }
        try {
            # Windows PowerShell can strip embedded quotes in native arguments.
            # Parse version output instead of passing JavaScript through -e.
            $VersionOutput = & $Candidate --version
            $VersionExitCode = $LASTEXITCODE
            $VersionMatch = [regex]::Match(($VersionOutput -join "`n").Trim(), '^v(\d+\.\d+\.\d+)$')
            if ($VersionExitCode -eq 0 -and $VersionMatch.Success -and
                ([version]$VersionMatch.Groups[1].Value -ge [version]'22.12.0') -and
                (Test-Path -LiteralPath (Join-Path (Split-Path -Parent $Candidate) 'npm.cmd'))) { return $Candidate }
        } catch { } # Try other installations when an executable is broken.
    }
}

function Install-LocalNode {
    $Architecture = $env:PROCESSOR_ARCHITECTURE
    if ($env:PROCESSOR_ARCHITEW6432) { $Architecture = $env:PROCESSOR_ARCHITEW6432 }
    switch ($Architecture) {
        'AMD64' { $NodeArch = 'x64' }
        'ARM64' { $NodeArch = 'arm64' }
        'x86' { $NodeArch = 'x86' }
        default { throw "Unsupported Windows architecture: $Architecture" }
    }
    # Official portable distribution: no MSI registration or administrator needed.
    $BaseUrl = 'https://nodejs.org/dist/latest-v22.x'
    $ToolDirectory = Join-Path $ProjectRoot '.tools\node'
    New-Item -ItemType Directory -Path $ToolDirectory -Force | Out-Null
    $DownloadDirectory = Join-Path $ToolDirectory ([guid]::NewGuid().ToString())
    New-Item -ItemType Directory -Path $DownloadDirectory | Out-Null
    $PreviousProtocol = [Net.ServicePointManager]::SecurityProtocol
    try {
        [Net.ServicePointManager]::SecurityProtocol = $PreviousProtocol -bor [Net.SecurityProtocolType]::Tls12
        Write-Host 'Downloading official Node.js 22 portable runtime...'
        $Checksums = (Invoke-WebRequest "$BaseUrl/SHASUMS256.txt" -UseBasicParsing).Content
        $Entry = [regex]::Match([string]$Checksums, "(?m)^([a-fA-F0-9]{64})\s+(node-v22\.[0-9]+\.[0-9]+-win-$NodeArch\.zip)\s*$")
        if (!$Entry.Success) { throw "Official checksum list has no Windows $NodeArch ZIP." }
        $ArchiveName = $Entry.Groups[2].Value
        $ArchivePath = Join-Path $DownloadDirectory $ArchiveName
        Invoke-WebRequest "$BaseUrl/$ArchiveName" -UseBasicParsing -OutFile $ArchivePath
        if ((Get-FileHash -LiteralPath $ArchivePath -Algorithm SHA256).Hash -ne $Entry.Groups[1].Value) {
            throw 'Node.js download checksum mismatch. Rerun setup to download again.'
        }
        Expand-Archive -LiteralPath $ArchivePath -DestinationPath $ToolDirectory -Force
    } finally {
        [Net.ServicePointManager]::SecurityProtocol = $PreviousProtocol
        # This directory is created above with a fresh GUID under .tools/node.
        $ResolvedDownload = (Resolve-Path -LiteralPath $DownloadDirectory).Path
        $ResolvedTools = (Resolve-Path -LiteralPath $ToolDirectory).Path
        if ((Split-Path -Parent $ResolvedDownload) -ne $ResolvedTools) { throw 'Unexpected Node.js temporary directory path.' }
        Remove-Item -LiteralPath $ResolvedDownload -Recurse -Force
    }
}

Update-SetupPath
$Python = Find-Python
if (!$Python) {
    if ($env:PYTHON_BIN) { throw 'PYTHON_BIN must point to an existing Python 3.12+ executable. Correct or remove it, then rerun setup.' }
    Install-Prerequisite 'Python.Python.3.12'
    $Python = Find-Python
    if (!$Python) { throw 'Python installation completed but Python 3.12+ was not found. Reopen PowerShell and rerun setup.' }
}
$Node = Find-Node
if (!$Node) {
    try { Install-Prerequisite 'OpenJS.NodeJS.LTS' } catch {
        Write-Warning "Winget could not install Node.js: $($_.Exception.Message)"
    }
    $Node = Find-Node
    if (!$Node) {
        Install-LocalNode
        $Node = Find-Node
    }
    if (!$Node) { throw 'The downloaded Node.js runtime could not run. Check Windows architecture and security software.' }
}
# Put the validated installation first so npm and its child processes use it.
$NodeDirectory = Split-Path -Parent $Node
$env:Path = "$NodeDirectory;$env:Path"
# Use npm.cmd to avoid PowerShell execution-policy restrictions on npm.ps1.
$Npm = Join-Path $NodeDirectory 'npm.cmd'
if (!(Test-Path -LiteralPath $Npm)) { throw 'npm.cmd is missing next to Node.js. Repair the Node.js installation and rerun setup.' }
Write-Host "Using Python: $Python"
Write-Host "Using Node.js: $Node"
& $Python -m venv .venv-phase1
if ($LASTEXITCODE -ne 0) { throw 'Python environment creation failed' }
& .\.venv-phase1\Scripts\python.exe -m pip install -r apps/desktop/backend/requirements-dev.lock
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
& .\.venv-phase1\Scripts\python.exe -m pip install --no-deps -e apps/desktop/backend
if ($LASTEXITCODE -ne 0) { throw 'Backend installation failed' }
& .\.venv-phase1\Scripts\python.exe -m pip install hatchling
if ($LASTEXITCODE -ne 0) { throw 'Backend build tooling installation failed' }
& .\.venv-phase1\Scripts\python.exe apps/desktop/scripts/install-media-tools.py
if ($LASTEXITCODE -ne 0) { throw 'Media tool installation failed' }
# Launch npm through the selected Node executable and normalize the environment
# inherited by lifecycle scripts (including esbuild's `node install.js`).
$NpmRunner = Join-Path $PSScriptRoot 'run-npm.cjs'
& $Node $NpmRunner ci --prefix apps/desktop/frontend
if ($LASTEXITCODE -ne 0) { throw 'Frontend installation failed' }
& $Node $NpmRunner run build --prefix apps/desktop/frontend
if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed' }
Write-Host 'Setup complete. Run ./scripts/windows/3-run.ps1'

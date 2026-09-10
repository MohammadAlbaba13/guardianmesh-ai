$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
        python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Python environment creation failed. Install Python 3.12+.' }
    }
    & '.\.venv\Scripts\python.exe' -m pip install -r backend\requirements.lock.txt
    if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
    Push-Location (Join-Path $projectRoot 'frontend')
    try {
        npm ci
        if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
    } finally { Pop-Location }
    Write-Host 'GuardianMesh dependencies installed. Run: .\scripts\start.ps1'
} finally { Pop-Location }

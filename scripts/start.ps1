$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
$vitePath = Join-Path $projectRoot 'frontend\node_modules\vite\bin\vite.js'
$nodePath = (Get-Command node -ErrorAction Stop).Source
$logsPath = Join-Path $projectRoot '.logs'
if (-not (Test-Path -LiteralPath $pythonPath) -or -not (Test-Path -LiteralPath $vitePath)) {
    throw 'Dependencies are missing. Run .\scripts\setup.ps1 first.'
}
New-Item -ItemType Directory -Path $logsPath -Force | Out-Null
$records = @()
$recordPath = Join-Path $logsPath 'processes.json'
if (Test-Path -LiteralPath $recordPath) { $records = @(Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json) }
function Save-ProcessRecords { ConvertTo-Json -InputObject @($records) -Depth 3 | Set-Content -LiteralPath $recordPath }
function Test-GuardianBackend {
    try { $health = Invoke-RestMethod 'http://127.0.0.1:8000/api/health' -TimeoutSec 2; return ($health.simulation -eq $true -and $health.agents -eq 6) }
    catch { return $false }
}
function Test-GuardianFrontend {
    try { $page = Invoke-WebRequest 'http://127.0.0.1:5173/' -UseBasicParsing -TimeoutSec 2; return $page.Content.Contains('GuardianMesh AI') }
    catch { return $false }
}
if (-not (Test-GuardianBackend)) {
    $backendProcess = Start-Process -FilePath $pythonPath -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000') -WorkingDirectory (Join-Path $projectRoot 'backend') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logsPath 'backend.out.log') -RedirectStandardError (Join-Path $logsPath 'backend.err.log') -PassThru
    $records += @{ id = $backendProcess.Id; kind = 'backend'; created_seconds = ([DateTimeOffset]$backendProcess.StartTime).ToUnixTimeSeconds() }
    Save-ProcessRecords
}
if (-not (Test-GuardianFrontend)) {
    $webProcess = Start-Process -FilePath $nodePath -ArgumentList @(('"' + $vitePath + '"'),'--host','127.0.0.1','--port','5173','--strictPort') -WorkingDirectory (Join-Path $projectRoot 'frontend') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logsPath 'frontend.out.log') -RedirectStandardError (Join-Path $logsPath 'frontend.err.log') -PassThru
    $records += @{ id = $webProcess.Id; kind = 'frontend'; created_seconds = ([DateTimeOffset]$webProcess.StartTime).ToUnixTimeSeconds() }
    Save-ProcessRecords
}
Save-ProcessRecords
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    if ((Test-GuardianBackend) -and (Test-GuardianFrontend)) {
        Write-Host 'GuardianMesh AI is ready: http://127.0.0.1:5173/'
        Write-Host 'API documentation: http://127.0.0.1:8000/docs'
        Write-Host 'Stop script-started servers with: .\scripts\stop.ps1'
        exit 0
    }
    Start-Sleep -Milliseconds 500
}
throw 'Startup did not complete. Inspect .logs\backend.err.log and .logs\frontend.err.log; ensure ports 8000 and 5173 are available.'

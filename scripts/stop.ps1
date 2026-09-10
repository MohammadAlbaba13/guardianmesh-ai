$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$recordPath = Join-Path $projectRoot '.logs\processes.json'
if (-not (Test-Path -LiteralPath $recordPath)) { Write-Host 'No script-started servers recorded.'; exit 0 }
$records = @(Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json)
foreach ($entry in $records) {
    if (-not $entry.id) { continue }
    $processId = [int]$entry.id
    $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $processId" -ErrorAction SilentlyContinue
    if (-not $processInfo) { continue }
    if ($entry.created_seconds -and [Math]::Abs(([DateTimeOffset]$processInfo.CreationDate).ToUnixTimeSeconds() - $entry.created_seconds) -gt 2) { continue }
    $ownedBackend = $entry.kind -eq 'backend' -and $processInfo.ExecutablePath -eq (Join-Path $projectRoot '.venv\Scripts\python.exe') -and $processInfo.CommandLine.Contains('app.main:app')
    $ownedFrontend = $entry.kind -eq 'frontend' -and $processInfo.CommandLine.Contains((Join-Path $projectRoot 'frontend\node_modules\vite\bin\vite.js'))
    if ($ownedBackend -or $ownedFrontend) {
        # Windows virtualenv python.exe launches the base interpreter as a child.
        # Validate the parent above, then stop only its same-command descendants.
        $children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId = $processId" -ErrorAction SilentlyContinue)
        foreach ($child in $children) {
            if ($ownedBackend -and $child.Name -eq 'python.exe' -and $child.CommandLine.Contains('app.main:app') -and $child.CreationDate -ge $processInfo.CreationDate) {
                Stop-Process -Id $child.ProcessId -ErrorAction SilentlyContinue
                Wait-Process -Id $child.ProcessId -Timeout 5 -ErrorAction SilentlyContinue
                if (Get-Process -Id $child.ProcessId -ErrorAction SilentlyContinue) { throw 'The backend child did not stop. Ownership records have been retained.' }
            }
        }
        Stop-Process -Id $processId -ErrorAction SilentlyContinue
        Wait-Process -Id $processId -Timeout 5 -ErrorAction SilentlyContinue
        if (Get-Process -Id $processId -ErrorAction SilentlyContinue) { throw 'A server did not stop. Ownership records have been retained.' }
        Write-Host "Stopped GuardianMesh $($entry.kind) process."
    }
}
Set-Content -LiteralPath $recordPath -Value '[]'

. (Join-Path $PSScriptRoot 'common.ps1')
$recordPath = Join-Path $ProjectRoot 'work\dev-processes.json'
if (-not (Test-Path -LiteralPath $recordPath)) { Write-Host 'No recorded project services.'; return }
$records = @(Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json)
foreach ($record in $records) {
    $p = Get-Process -Id $record.id -ErrorAction SilentlyContinue
    if ($p -and $p.StartTime.ToUniversalTime().Ticks.ToString() -eq $record.started) {
        # Only the verified process tree that this project's start script recorded.
        & taskkill.exe /PID $p.Id /T /F | Out-Null
    }
}
Set-Content -LiteralPath $recordPath -Value '[]' -Encoding utf8
Write-Host 'Recorded project services stopped.'

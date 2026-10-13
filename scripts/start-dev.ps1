param([switch]$WithLocalLLM)
. (Join-Path $PSScriptRoot 'common.ps1')
Set-Location -LiteralPath $ProjectRoot
$python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Run scripts\setup.ps1 first.' }
$node = Find-ProjectTool 'node' (Join-Path $RuntimeRoot 'node\bin\node.exe')
$env:PATH = (Split-Path -Parent $node) + ';' + $env:PATH
$env:NEXT_TELEMETRY_DISABLED = '1'
$port = [int](Read-ProjectSetting 'BACKEND_PORT' '9000')
$api = "http://127.0.0.1:$port"
$nextCli = Join-Path $ProjectRoot 'frontend\node_modules\next\dist\bin\next'
if (-not (Test-Path -LiteralPath $nextCli)) { throw 'Run scripts\setup.ps1 first.' }
$work = Join-Path $ProjectRoot 'work'
New-Item -ItemType Directory -Path $work -Force | Out-Null
$recordPath = Join-Path $work 'dev-processes.json'
$records = @()
if (Test-Path -LiteralPath $recordPath) { $records = @(Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json) }

function Save-Process($Process, [string]$Service) {
    $script:records += [pscustomobject]@{ id = $Process.Id; started = $Process.StartTime.ToUniversalTime().Ticks.ToString(); service = $Service }
    ConvertTo-Json -InputObject @($script:records) | Set-Content -LiteralPath $recordPath -Encoding utf8
}

if ($WithLocalLLM) {
    $base = Read-ProjectSetting 'OLLAMA_BASE_URL' 'http://127.0.0.1:11434'
    if (-not (Test-LocalService ($base.TrimEnd('/') + '/api/tags'))) {
        if ($base -ne 'http://127.0.0.1:11434') { throw 'For a custom Ollama URL, start that server separately.' }
        $ollama = Find-ProjectTool 'ollama' (Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe')
        $models = Read-ProjectSetting 'OLLAMA_MODELS_DIR' ''
        if (-not $models -or -not (Test-Path -LiteralPath $models)) { throw 'Set OLLAMA_MODELS_DIR to your existing Ollama model store in .env.' }
        $previousModels = $env:OLLAMA_MODELS
        $previousHost = $env:OLLAMA_HOST
        try {
            $env:OLLAMA_MODELS = $models
            $env:OLLAMA_HOST = '127.0.0.1:11434'
            $p = Start-Process -FilePath $ollama -ArgumentList 'serve' -WindowStyle Hidden -WorkingDirectory $ProjectRoot -RedirectStandardOutput (Join-Path $work 'ollama.stdout.log') -RedirectStandardError (Join-Path $work 'ollama.stderr.log') -PassThru
            Save-Process $p 'ollama'
        } finally { $env:OLLAMA_MODELS = $previousModels; $env:OLLAMA_HOST = $previousHost }
    }
}
if (-not (Test-LocalService ($api + '/api/health'))) {
    $p = Start-Process -FilePath $python -ArgumentList @('-m', 'uvicorn', 'backend.app.main:app', '--host', '127.0.0.1', '--port', $port.ToString()) -WindowStyle Hidden -WorkingDirectory $ProjectRoot -RedirectStandardOutput (Join-Path $work 'backend.stdout.log') -RedirectStandardError (Join-Path $work 'backend.stderr.log') -PassThru
    Save-Process $p 'backend'
}
if (-not (Test-LocalService 'http://127.0.0.1:3000')) {
    $p = Start-Process -FilePath $node -ArgumentList @(('"' + $nextCli + '"'), 'dev', '--webpack', '--hostname', '127.0.0.1', '--port', '3000') -WindowStyle Hidden -WorkingDirectory (Join-Path $ProjectRoot 'frontend') -RedirectStandardOutput (Join-Path $work 'frontend.stdout.log') -RedirectStandardError (Join-Path $work 'frontend.stderr.log') -PassThru
    Save-Process $p 'frontend'
}
Write-Host 'Services are starting. Dashboard: http://127.0.0.1:3000'
Write-Host "API: $api/docs | Logs: work\*.log"
Write-Host 'Stop these services with scripts\stop-dev.ps1.'

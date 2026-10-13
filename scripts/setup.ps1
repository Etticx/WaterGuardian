. (Join-Path $PSScriptRoot 'common.ps1')
Set-Location -LiteralPath $ProjectRoot
$python = Find-ProjectTool 'python' (Join-Path $RuntimeRoot 'python\python.exe')
$node = Find-ProjectTool 'node' (Join-Path $RuntimeRoot 'node\bin\node.exe')
$pnpm = Find-ProjectTool 'pnpm' (Join-Path $RuntimeRoot 'bin\fallback\pnpm.cmd')
$env:PATH = (Split-Path -Parent $node) + ';' + $env:PATH
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    & $python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python environment creation failed.' }
}
& '.\.venv\Scripts\python.exe' -m pip install -r backend/requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }
if (-not (Test-Path -LiteralPath '.env')) { Copy-Item -LiteralPath '.env.example' -Destination '.env' }
if (-not (Test-Path -LiteralPath 'frontend\.env.local')) { Copy-Item -LiteralPath 'frontend\.env.example' -Destination 'frontend\.env.local' }
Push-Location -LiteralPath 'frontend'
try {
    & $pnpm install --frozen-lockfile
    if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
} finally { Pop-Location }
Write-Host 'Setup complete. Add provider keys to .env, then run scripts\start-dev.ps1.'

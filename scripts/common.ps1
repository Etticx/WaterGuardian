$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$RuntimeRoot = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies'

function Find-ProjectTool([string]$Name, [string]$Fallback) {
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($command -and $command.Source -notmatch 'Microsoft\\WindowsApps') { return $command.Source }
    if (Test-Path -LiteralPath $Fallback) { return $Fallback }
    throw "Install $Name and add it to PATH, then run this script again."
}

function Read-ProjectSetting([string]$Name, [string]$Default) {
    $path = Join-Path $ProjectRoot '.env'
    if (Test-Path -LiteralPath $path) {
        $line = Get-Content -LiteralPath $path | Where-Object { $_ -match ('^' + [regex]::Escape($Name) + '=') } | Select-Object -Last 1
        if ($line) { return (($line -split '=', 2)[1]).Trim().Trim('"').Trim("'") }
    }
    return $Default
}

function Test-LocalService([string]$Url) {
    try { Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2 | Out-Null; return $true }
    catch { return $false }
}

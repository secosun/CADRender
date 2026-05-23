#Requires -Version 5.1
<#
.SYNOPSIS
  Register DeepSeek proxy to start at Windows logon (for Claude Code).

.USAGE
  powershell -ExecutionPolicy Bypass -File install_deepseek_proxy_startup.ps1

  Optional: first-time deps
    python -m venv .venv-proxy
    .\.venv-proxy\Scripts\pip install -r requirements-proxy.txt
    copy .env.example .env   # set DEEPSEEK_API_KEY
#>
$ErrorActionPreference = "Stop"

$TaskName = "CADRender-DeepSeek-Proxy"
$StartScript = Join-Path $PSScriptRoot "start_deepseek_proxy.ps1"

if (-not (Test-Path $StartScript)) {
    Write-Error "Not found: $StartScript"
}

# One-shot: create venv + deps if missing
$venvPy = Join-Path $PSScriptRoot ".venv-proxy\Scripts\python.exe"
$reqFile = Join-Path $PSScriptRoot "requirements-proxy.txt"
if (-not (Test-Path $venvPy) -and (Test-Path $reqFile)) {
    Write-Host "Creating .venv-proxy and installing dependencies (first run)..."
    $savedProxy = $env:HTTP_PROXY, $env:HTTPS_PROXY, $env:ALL_PROXY
    $env:HTTP_PROXY = $null
    $env:HTTPS_PROXY = $null
    $env:ALL_PROXY = $null
    try {
        $py = if (Test-Path "C:\Python314\python.exe") { "C:\Python314\python.exe" } else { "python" }
    & $py -m venv (Join-Path $PSScriptRoot ".venv-proxy")
        & (Join-Path $PSScriptRoot ".venv-proxy\Scripts\pip.exe") install -r $reqFile -q -i https://pypi.tuna.tsinghua.edu.cn/simple
    } finally {
        if ($savedProxy[0]) { $env:HTTP_PROXY = $savedProxy[0] } else { Remove-Item Env:HTTP_PROXY -ErrorAction SilentlyContinue }
        if ($savedProxy[1]) { $env:HTTPS_PROXY = $savedProxy[1] } else { Remove-Item Env:HTTPS_PROXY -ErrorAction SilentlyContinue }
        if ($savedProxy[2]) { $env:ALL_PROXY = $savedProxy[2] } else { Remove-Item Env:ALL_PROXY -ErrorAction SilentlyContinue }
    }
}

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$StartScript`"" `
    -WorkingDirectory $PSScriptRoot

$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Claude Code local proxy → DeepSeek (http://127.0.0.1:8099)" `
    -RunLevel Limited | Out-Null

Write-Host "Registered scheduled task: $TaskName"
Write-Host "  Runs at logon for user: $env:USERNAME"
Write-Host "  Script: $StartScript"
Write-Host ""
Write-Host "Claude Code should use (~/.claude/settings.json):"
Write-Host '  "ANTHROPIC_BASE_URL": "http://localhost:8099"'
Write-Host ""
Write-Host "Test now:"
Write-Host "  powershell -ExecutionPolicy Bypass -File start_deepseek_proxy.ps1"
Write-Host "  curl http://127.0.0.1:8099/health"

# Run once immediately
& $StartScript

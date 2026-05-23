# Start local DeepSeek proxy for Claude Code (ANTHROPIC_BASE_URL=http://localhost:8099)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$logDir = Join-Path $env:LOCALAPPDATA "CADRender"
$logFile = Join-Path $logDir "deepseek_proxy.log"
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

# Load .env into process environment
$envFile = Join-Path $PSScriptRoot ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line -match "^\s*([^=]+)=(.*)$") {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim().Trim('"').Trim("'")
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

if (-not $env:DEEPSEEK_API_KEY -and $env:ANTHROPIC_API_KEY) {
    $env:DEEPSEEK_API_KEY = $env:ANTHROPIC_API_KEY
}

# Fallback: Claude Code settings (~/.claude/settings.json)
if (-not $env:DEEPSEEK_API_KEY) {
    $claudeSettings = Join-Path $env:USERPROFILE ".claude\settings.json"
    if (Test-Path $claudeSettings) {
        try {
            $cfg = Get-Content $claudeSettings -Raw -Encoding UTF8 | ConvertFrom-Json
            $key = $cfg.env.ANTHROPIC_API_KEY
            if ($key) { $env:DEEPSEEK_API_KEY = $key }
        } catch {}
    }
}

if (-not $env:DEEPSEEK_API_KEY) {
    Write-Error "DEEPSEEK_API_KEY not set. Add to .env or ~/.claude/settings.json env.ANTHROPIC_API_KEY"
    exit 1
}

try {
    $health = Invoke-WebRequest -Uri "http://127.0.0.1:8099/health" -TimeoutSec 2 -UseBasicParsing
    if ($health.StatusCode -eq 200) {
        exit 0
    }
} catch {}

# Prefer Python 3.14 (known to have proxy deps); .venv-proxy optional
$pythonExe = "python"
$pythonArgs = @()
if (Test-Path "C:\Python314\python.exe") {
    $pythonExe = "C:\Python314\python.exe"
} else {
    $venvPy = Join-Path $PSScriptRoot ".venv-proxy\Scripts\python.exe"
    if (Test-Path $venvPy) { $pythonExe = $venvPy }
}

$proxyScript = Join-Path $PSScriptRoot "deepseek_proxy.py"
if (-not (Test-Path $proxyScript)) {
    Write-Error "Missing deepseek_proxy.py in $PSScriptRoot"
    exit 1
}

function Write-ProxyLog([string]$msg) {
    try {
        Add-Content -Path $logFile -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $msg" -ErrorAction SilentlyContinue
    } catch {}
}

Write-ProxyLog "Starting proxy..."

# Prevent child Python from using broken system proxy for api.deepseek.com
$env:HTTP_PROXY = $null
$env:HTTPS_PROXY = $null
$env:ALL_PROXY = $null
$env:NO_PROXY = "localhost,127.0.0.1"

$procArgs = $pythonArgs + @("-u", $proxyScript)
Start-Process -FilePath $pythonExe -ArgumentList $procArgs -WorkingDirectory $PSScriptRoot `
    -WindowStyle Hidden -RedirectStandardOutput $logFile -RedirectStandardError ($logFile + ".err")

Start-Sleep -Seconds 3
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:8099/health" -TimeoutSec 10 -UseBasicParsing
    Write-ProxyLog "OK $($r.Content)"
    exit 0
} catch {
    Write-ProxyLog "FAILED: $_"
    exit 1
}

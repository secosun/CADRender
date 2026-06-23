# Load CADRender environment from docs/environment_config.md and .env into the current session.
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Loader = Join-Path $PSScriptRoot "load_calibration_env.py"

if (-not (Test-Path $Loader)) {
    Write-Error "Missing $Loader"
}

$exports = python $Loader --export ps1
if ($LASTEXITCODE -ne 0) {
    Write-Error "load_calibration_env.py failed"
}

foreach ($line in $exports) {
    if ($line.Trim()) {
        Invoke-Expression $line
    }
}

Write-Host "CADRender env loaded from docs/environment_config.md (+ .env if present)"

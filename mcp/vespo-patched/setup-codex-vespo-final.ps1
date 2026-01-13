# Wrapper for the single-source setup script.

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SetupScript = Join-Path $ScriptDir "setup-codex-vespo.js"

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Error "node is required to run $SetupScript"
    exit 1
}

& node $SetupScript
exit $LASTEXITCODE

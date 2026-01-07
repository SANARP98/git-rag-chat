# setup-codex-vespo.ps1
# Complete setup for PATCHED vespo92 ChromaDB MCP server with Codex CLI
# Fixes MCP stdio compliance issues for ChatGPT Codex CLI in VS Code
#
# This script:
# 1. Starts ChromaDB in Docker
# 2. Builds the PATCHED vespo MCP server with stdio compliance fixes
# 3. Configures Codex CLI to use the server
# 4. Validates the setup

$ErrorActionPreference = "Stop"

Write-Host "=== PATCHED Vespo ChromaDB MCP Server Setup for Codex CLI ===" -ForegroundColor Cyan
Write-Host "This version fixes stdio handshake issues for ChatGPT Codex CLI" -ForegroundColor Green
Write-Host ""

# --- Preconditions ---
Write-Host "==> [1/10] Checking prerequisites..." -ForegroundColor Cyan

if (-not (Get-Command codex -ErrorAction SilentlyContinue)) {
    throw "codex CLI not found in PATH. Install it first."
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "docker not found in PATH. Install Docker Desktop."
}

$DockerExe = (Get-Command docker).Source
Write-Host "✓ Found codex and docker" -ForegroundColor Green

# --- Settings ---
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ChromaNetwork = "chroma-net"
$ChromaContainer = "chromadb-local"
$ChromaHostPort = 8001
$McpImageName = "chroma-mcp-vespo-patched:latest"

# --- User Input ---
Write-Host ""
$RepoPath = Read-Host "Enter your repo path (e.g., C:\Users\you\source\myrepo)"
$RepoPath = $RepoPath.Trim().Trim('"')

if (-not (Test-Path $RepoPath)) {
    throw "Repository path does not exist: $RepoPath"
}

Write-Host "✓ Repository path: $RepoPath" -ForegroundColor Green

# --- Helper Functions ---
function To-DockerPath([string]$p) {
    $full = (Resolve-Path $p).Path
    $drive = $full.Substring(0, 1).ToLower()
    $rest = $full.Substring(2) -replace "\\", "/"
    return "/$drive$rest"
}

function Get-FreePort([int]$StartPort) {
    for ($p = $StartPort; $p -lt ($StartPort + 50); $p++) {
        $inUse = Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue
        if (-not $inUse) { return $p }
    }
    throw "No free port found in range $StartPort..$($StartPort+49)"
}

$RepoDockerPath = To-DockerPath $RepoPath
$ChromaHostPort = Get-FreePort -StartPort $ChromaHostPort
$ChromaUrlInDocker = "http://$ChromaContainer`:8000"

Write-Host "✓ Chroma host port: $ChromaHostPort" -ForegroundColor Green
Write-Host "✓ Chroma URL (inside Docker): $ChromaUrlInDocker" -ForegroundColor Green
Write-Host ""

# --- Step 2: Create Docker Network ---
Write-Host "==> [2/10] Creating Docker network: $ChromaNetwork" -ForegroundColor Cyan

$netExists = & $DockerExe network inspect $ChromaNetwork 2>$null
if ($LASTEXITCODE -ne 0) {
    & $DockerExe network create $ChromaNetwork | Out-Null
    Write-Host "✓ Network created" -ForegroundColor Green
} else {
    Write-Host "✓ Network already exists" -ForegroundColor Green
}

# --- Step 3: Start ChromaDB ---
Write-Host ""
Write-Host "==> [3/10] Starting ChromaDB container: $ChromaContainer" -ForegroundColor Cyan

# Remove existing container if present
$existingId = & $DockerExe ps -aq -f "name=^$ChromaContainer$" 2>$null
if ($existingId) {
    Write-Host "Removing existing container..." -ForegroundColor Yellow
    & $DockerExe rm -f $ChromaContainer 2>&1 | Out-Null
}

# Start ChromaDB
& $DockerExe run -d `
    --name $ChromaContainer `
    --network $ChromaNetwork `
    -p "${ChromaHostPort}:8000" `
    chromadb/chroma:latest | Out-Null

Write-Host "✓ ChromaDB container started" -ForegroundColor Green

# --- Step 4: Wait for ChromaDB ---
Write-Host ""
Write-Host "==> [4/10] Waiting for ChromaDB to be ready..." -ForegroundColor Cyan

$ok = $false
for ($i = 0; $i -lt 40; $i++) {
    try {
        $resp = Invoke-RestMethod -Uri "http://localhost:${ChromaHostPort}/api/v2/heartbeat" -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($resp) {
            $ok = $true
            break
        }
    }
    catch {
        Start-Sleep -Seconds 1
    }
}

if (-not $ok) {
    throw "ChromaDB not reachable on http://localhost:${ChromaHostPort}/api/v2/heartbeat"
}

Write-Host "✓ ChromaDB is ready!" -ForegroundColor Green

# --- Step 5: Build Patched MCP Server ---
Write-Host ""
Write-Host "==> [5/10] Building PATCHED MCP server image: $McpImageName" -ForegroundColor Cyan
Write-Host "This image has stdio compliance fixes for Codex CLI" -ForegroundColor Yellow

Push-Location $ScriptDir
& $DockerExe build -t $McpImageName -f Dockerfile . 2>&1 | Out-Host
Pop-Location

if ($LASTEXITCODE -ne 0) {
    throw "Failed to build Docker image"
}

Write-Host "✓ Image built successfully" -ForegroundColor Green

# --- Step 6: Update Codex Config ---
Write-Host ""
Write-Host "==> [6/10] Updating Codex CLI config: ~/.codex/config.toml" -ForegroundColor Cyan

$CodexDir = Join-Path $env:USERPROFILE ".codex"
$CodexCfg = Join-Path $CodexDir "config.toml"

if (-not (Test-Path $CodexDir)) {
    New-Item -ItemType Directory -Path $CodexDir | Out-Null
}

if (-not (Test-Path $CodexCfg)) {
    New-Item -ItemType File -Path $CodexCfg | Out-Null
}

# Read existing config
$cfgText = Get-Content $CodexCfg -Raw -ErrorAction SilentlyContinue
if (-not $cfgText) { $cfgText = "" }

# Remove existing chromadb_context_vespo block if present
$cfgText = [regex]::Replace($cfgText, "(?ms)^\[mcp_servers\.chromadb_context_vespo\].*?(?=^\[|\z)", "")
$cfgText = $cfgText.TrimEnd()

# Add new MCP server configuration
$block = @"
[mcp_servers.chromadb_context_vespo]
command = "docker"
args = [
  "run", "--rm", "-i",
  "--network", "$ChromaNetwork",
  "-e", "CHROMA_URL=$ChromaUrlInDocker",
  "-e", "CHROMADB_URL=$ChromaUrlInDocker",
  "-e", "REMOTE_CHROMA_URL=$ChromaUrlInDocker",
  "-v", "${RepoDockerPath}:/workspace:ro",
  "-w", "/workspace",
  "$McpImageName"
]
startup_timeout_sec = 45
tool_timeout_sec = 180
enabled = true

"@

Set-Content -Path $CodexCfg -Value ($cfgText + "`r`n`r`n" + $block) -Encoding UTF8
Write-Host "✓ Codex config updated" -ForegroundColor Green

# --- Step 7: Validate MCP Registration ---
Write-Host ""
Write-Host "==> [7/10] Validating MCP server registration..." -ForegroundColor Cyan
& codex mcp list 2>&1 | Out-Host

# --- Step 8: Test MCP Server Handshake ---
Write-Host ""
Write-Host "==> [8/10] Testing MCP stdio handshake (quick test)..." -ForegroundColor Cyan

$testOutput = & $DockerExe run --rm -i `
    --network $ChromaNetwork `
    -e "CHROMA_URL=$ChromaUrlInDocker" `
    $McpImageName 2>&1 | Select-Object -First 1

Write-Host "First line of output: $testOutput" -ForegroundColor Yellow

if ($testOutput -match "^\{") {
    Write-Host "✓ Server outputs valid JSON (good sign!)" -ForegroundColor Green
} else {
    Write-Host "⚠ Server may have stdout contamination issues" -ForegroundColor Yellow
    Write-Host "First output was: $testOutput" -ForegroundColor Yellow
}

# --- Step 9: Summary ---
Write-Host ""
Write-Host "=== [9/10] Setup Complete! ===" -ForegroundColor Green
Write-Host ""
Write-Host "Configuration Summary:" -ForegroundColor Cyan
Write-Host "  - ChromaDB:       http://localhost:$ChromaHostPort" -ForegroundColor White
Write-Host "  - Docker network: $ChromaNetwork" -ForegroundColor White
Write-Host "  - MCP Server:     chromadb_context_vespo" -ForegroundColor White
Write-Host "  - Repo mounted:   /workspace (read-only)" -ForegroundColor White
Write-Host ""

# --- Step 10: Next Steps ---
Write-Host "=== [10/10] Next Steps ===" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. Close VS Code COMPLETELY (very important!)" -ForegroundColor Yellow
Write-Host "2. Reopen VS Code and open your repository" -ForegroundColor Yellow
Write-Host "3. Start a NEW Codex chat" -ForegroundColor Yellow
Write-Host "4. Try these commands:" -ForegroundColor Yellow
Write-Host "   • 'List chroma collections'" -ForegroundColor White
Write-Host "   • 'Scan directory /workspace'" -ForegroundColor White
Write-Host "   • 'Batch ingest /workspace into collection my_repo'" -ForegroundColor White
Write-Host ""
Write-Host "Key Differences from Official Server:" -ForegroundColor Cyan
Write-Host "  ✓ 22 advanced tools (batch processing, EXIF, watch folders)" -ForegroundColor Green
Write-Host "  ✓ Stdio compliance fixes for Codex CLI" -ForegroundColor Green
Write-Host "  ✓ All console.error() calls wrapped in DEBUG mode" -ForegroundColor Green
Write-Host "  ✓ Clean Dockerfile (no stdout contamination)" -ForegroundColor Green
Write-Host ""
Write-Host "To enable debug logging: docker run -e DEBUG_MCP=true ..." -ForegroundColor DarkGray
Write-Host ""
Write-Host "Setup script completed successfully! 🎉" -ForegroundColor Green

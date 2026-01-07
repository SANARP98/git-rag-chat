# chromamcp.ps1
# One-shot setup for:
# - ChromaDB (Docker)
# - Official Chroma MCP server (mcp/chroma) for Codex CLI / VS Code
# - Updates ~/.codex/config.toml with a working stdio MCP entry

$ErrorActionPreference = "Stop"

function Exec-Native {
  param(
    [Parameter(Mandatory=$true)][string]$File,
    [Parameter(Mandatory=$true)][string[]]$Args,
    [switch]$IgnoreError
  )
  $out = & $File @Args 2>$null
  $code = $LASTEXITCODE
  if (-not $IgnoreError -and $code -ne 0) {
    throw "Command failed ($code): $File $($Args -join ' ')"
  }
  return $out
}

Write-Host "==> [0/8] Preconditions" -ForegroundColor Cyan

# codex
if (-not (Get-Command codex -ErrorAction SilentlyContinue)) { throw "codex CLI not found in PATH" }

# docker
$dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
if (-not $dockerCmd) { throw "docker not found in PATH. Install Docker Desktop." }
$DockerExe = $dockerCmd.Source

# git (only needed if your workflow uses it; leaving as optional)
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  Write-Host "NOTE: git not found (optional). Continuing..." -ForegroundColor Yellow
}

# --- USER INPUT ---
$RepoPath = Read-Host "Enter your repo path (example: C:\Users\you\source\myrepo)"
$RepoPath = $RepoPath.Trim().Trim('"')

if (-not (Test-Path $RepoPath)) { throw "RepoPath does not exist: $RepoPath" }

# --- SETTINGS ---
$ChromaNetwork   = "chroma-net"
$ChromaContainer = "chromadb-local"
$ChromaHostPort  = 8001  # starting port; script will bump if in use

Write-Host "RepoPath: $RepoPath" -ForegroundColor Green
Write-Host "Docker:   $DockerExe" -ForegroundColor Green

# Find a free port starting from 8001
function Get-FreePort {
  param([int]$StartPort)
  for ($p = $StartPort; $p -lt ($StartPort + 50); $p++) {
    $inUse = Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue
    if (-not $inUse) { return $p }
  }
  throw "No free port found in range $StartPort..$($StartPort+49)"
}
$ChromaHostPort = Get-FreePort -StartPort $ChromaHostPort

Write-Host "Chroma host port: $ChromaHostPort (http://localhost:$ChromaHostPort)" -ForegroundColor Green
Write-Host "Chroma URL (inside Docker network): http://$ChromaContainer`:8000" -ForegroundColor Green

Write-Host "==> [1/8] Ensure docker network exists: $ChromaNetwork" -ForegroundColor Cyan
# create network if missing
Exec-Native -File $DockerExe -Args @("network","inspect",$ChromaNetwork) -IgnoreError | Out-Null
if ($LASTEXITCODE -ne 0) {
  Exec-Native -File $DockerExe -Args @("network","create",$ChromaNetwork) | Out-Null
}

Write-Host "==> [2/8] Ensure ChromaDB container is running: $ChromaContainer" -ForegroundColor Cyan

# If container exists, remove it (safe)
$existingId = Exec-Native -File $DockerExe -Args @("ps","-aq","-f","name=^$ChromaContainer$") -IgnoreError
if ($existingId) {
  Exec-Native -File $DockerExe -Args @("rm","-f",$ChromaContainer) -IgnoreError | Out-Null
}

# Start ChromaDB
Exec-Native -File $DockerExe -Args @(
  "run","-d",
  "--name",$ChromaContainer,
  "--network",$ChromaNetwork,
  "-p","$ChromaHostPort`:8000",
  "chromadb/chroma:latest"
) | Out-Null

Write-Host "==> Waiting for Chroma v2 heartbeat..." -ForegroundColor Cyan
$ok = $false
for ($i=0; $i -lt 40; $i++) {
  try {
    $resp = Invoke-RestMethod -Uri "http://localhost:$ChromaHostPort/api/v2/heartbeat" -TimeoutSec 2
    if ($resp) { $ok = $true; break }
  } catch {
    Start-Sleep -Seconds 1
  }
}
if (-not $ok) { throw "ChromaDB not reachable on http://localhost:$ChromaHostPort/api/v2/heartbeat" }
Write-Host "✅ Chroma reachable." -ForegroundColor Green

Write-Host "==> [3/8] Update Codex config: ~/.codex/config.toml" -ForegroundColor Cyan
$CodexDir = Join-Path $env:USERPROFILE ".codex"
$CodexCfg = Join-Path $CodexDir "config.toml"
if (-not (Test-Path $CodexDir)) { New-Item -ItemType Directory -Path $CodexDir | Out-Null }
if (-not (Test-Path $CodexCfg)) { New-Item -ItemType File -Path $CodexCfg | Out-Null }

function To-DockerPath([string]$p) {
  $full = (Resolve-Path $p).Path
  $drive = $full.Substring(0,1).ToLower()
  $rest = $full.Substring(2) -replace "\\","/"
  return "/$drive$rest"
}
$RepoDockerPath = To-DockerPath $RepoPath

# Remove existing block (if any)
$cfgText = Get-Content $CodexCfg -Raw
$cfgText = [regex]::Replace($cfgText, "(?ms)^\[mcp_servers\.chromadb_context\].*?(?=^\[|\z)", "")
$cfgText = $cfgText.TrimEnd()

# Add NEW working MCP server: official image `mcp/chroma`
# Use env vars to configure the server to connect to your local ChromaDB over the Docker network.
$block = @"
[mcp_servers.chromadb_context]
command = "docker"
args = [
  "run","--rm","-i",
  "--network","$ChromaNetwork",
  "-e","CHROMA_CLIENT_TYPE=http",
  "-e","CHROMA_HOST=$ChromaContainer",
  "-e","CHROMA_PORT=8000",
  "-v","${RepoDockerPath}:/workspace:ro",
  "-w","/workspace",
  "mcp/chroma"
]
startup_timeout_sec = 45
tool_timeout_sec = 180
enabled = true

"@

Set-Content -Path $CodexCfg -Value ($cfgText + "`r`n`r`n" + $block) -Encoding UTF8
Write-Host "✅ Codex config updated: $CodexCfg" -ForegroundColor Green

Write-Host "==> [4/8] Pull MCP server image (first time only)" -ForegroundColor Cyan
Exec-Native -File $DockerExe -Args @("pull","mcp/chroma") -IgnoreError | Out-Null

Write-Host "==> [5/8] Validate MCP entry appears in Codex" -ForegroundColor Cyan
Exec-Native -File "codex" -Args @("mcp","list") -IgnoreError

Write-Host ""
Write-Host "==> [6/8] DONE" -ForegroundColor Green
Write-Host "ChromaDB UI/API: http://localhost:$ChromaHostPort" -ForegroundColor Green
Write-Host "Repo mounted read-only in MCP container at: /workspace" -ForegroundColor Green
Write-Host ""
Write-Host "==> [7/8] Next steps" -ForegroundColor Yellow
Write-Host "1) Quit VS Code fully and reopen (important)." -ForegroundColor Yellow
Write-Host "2) Open a NEW Codex chat." -ForegroundColor Yellow
Write-Host "3) Try: 'List chroma collections' or 'Create a collection named test and add a doc'." -ForegroundColor Yellow

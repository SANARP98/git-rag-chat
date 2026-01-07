# chromamcp.ps1
# One-shot setup: ChromaDB (docker), MCP server (docker with Bun), Codex MCP config update
# Fixes: quoted paths, `${}` for : mounts, missing container rm, port already allocated.

$ErrorActionPreference = "Stop"

Write-Host "==> [0/9] Preconditions" -ForegroundColor Cyan
if (-not (Get-Command codex -ErrorAction SilentlyContinue)) { throw "codex CLI not found in PATH" }
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw "docker not found in PATH. Install Docker Desktop and ensure docker.exe is available." }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw "git not found in PATH. Install Git for Windows." }

# --- USER INPUT ---
$RepoPath = Read-Host "Enter your repo path (example: C:\Users\you\source\myrepo)"
$RepoPath = $RepoPath.Trim().Trim('"')
if (-not (Test-Path $RepoPath)) { throw "RepoPath does not exist: $RepoPath" }

# --- SETTINGS ---
$McpDir          = Join-Path $env:USERPROFILE "codex-chroma-mcp-server"
$ChromaNetwork   = "chroma-net"
$ChromaContainer = "chromadb-local"

# Host port range to try (avoid port-in-use crash)
$PreferredPort = 8001
$MaxPortTries  = 20

# Docker-internal URL (MCP should use this; it's stable)
$ChromaUrlInDocker = "http://$ChromaContainer`:8000"

# Pin image if you want (latest is ok for now)
$ChromaImage = "chromadb/chroma:latest"

function To-DockerPath([string]$p) {
  $full  = (Resolve-Path $p).Path
  $drive = $full.Substring(0,1).ToLower()
  $rest  = $full.Substring(2) -replace "\\","/"
  return "/$drive$rest"
}

function Test-LocalPortFree([int]$port) {
  # True = free, False = in use
  try {
    $conn = Test-NetConnection -ComputerName "127.0.0.1" -Port $port -WarningAction SilentlyContinue
    return (-not $conn.TcpTestSucceeded)
  } catch {
    # If Test-NetConnection is unavailable, assume free and let docker error reveal it
    return $true
  }
}

function Get-FreePort([int]$startPort, [int]$tries) {
  for ($p = $startPort; $p -lt ($startPort + $tries); $p++) {
    if (Test-LocalPortFree $p) { return $p }
  }
  throw "No free port found in range $startPort..$($startPort + $tries - 1)"
}

$RepoDockerPath = To-DockerPath $RepoPath

Write-Host "RepoPath: $RepoPath" -ForegroundColor Green
Write-Host "MCP repo dir: $McpDir" -ForegroundColor Green
Write-Host "Chroma URL (inside Docker network): $ChromaUrlInDocker" -ForegroundColor Green

Write-Host "==> [1/9] Ensure docker network exists: $ChromaNetwork" -ForegroundColor Cyan
$netExists = docker network ls --format '{{.Name}}' | Select-String -Quiet "^$ChromaNetwork$"
if (-not $netExists) { docker network create $ChromaNetwork | Out-Null }

Write-Host "==> [2/9] Ensure ChromaDB container is running: $ChromaContainer" -ForegroundColor Cyan

# If container exists, just ensure it's running. Otherwise create it.
$containerId = (docker ps -a --filter "name=^/$ChromaContainer$" --format "{{.ID}}" 2>$null)

if ($containerId) {
  Write-Host "Found existing container '$ChromaContainer' (id=$containerId). Ensuring it is running..." -ForegroundColor DarkYellow
  docker start $ChromaContainer *> $null 2>&1 | Out-Null
  # Determine what host port it's mapped to (if any)
  $portLine = docker port $ChromaContainer 8000 2>$null
  if ($portLine -match "0\.0\.0\.0:(\d+)" -or $portLine -match "127\.0\.0\.1:(\d+)") {
    $ChromaHostPort = [int]$matches[1]
    Write-Host "Chroma is already mapped to host port: $ChromaHostPort" -ForegroundColor Green
  } else {
    # No mapping found; pick a free port and recreate container with mapping
    Write-Host "Existing container has no host port mapping; recreating with a free port..." -ForegroundColor DarkYellow
    $ChromaHostPort = Get-FreePort $PreferredPort $MaxPortTries
    docker rm -f $ChromaContainer *> $null 2>&1 | Out-Null
    docker run -d --name $ChromaContainer `
      --network $ChromaNetwork `
      -p "$ChromaHostPort`:8000" `
      $ChromaImage | Out-Null
  }
} else {
  $ChromaHostPort = Get-FreePort $PreferredPort $MaxPortTries
  Write-Host "Using free host port: $ChromaHostPort" -ForegroundColor Green
  docker run -d --name $ChromaContainer `
    --network $ChromaNetwork `
    -p "$ChromaHostPort`:8000" `
    $ChromaImage | Out-Null
}

Write-Host "==> Waiting for Chroma v2 heartbeat on host port $ChromaHostPort..." -ForegroundColor Cyan
$ok = $false
for ($i=0; $i -lt 60; $i++) {
  try {
    $resp = Invoke-RestMethod -Uri "http://localhost:$ChromaHostPort/api/v2/heartbeat" -TimeoutSec 2
    if ($resp) { $ok = $true; break }
  } catch { Start-Sleep -Seconds 1 }
}
if (-not $ok) { throw "ChromaDB not reachable on http://localhost:$ChromaHostPort/api/v2/heartbeat" }
Write-Host "✅ Chroma reachable." -ForegroundColor Green

Write-Host "==> [3/9] Clone MCP repo fresh into: $McpDir" -ForegroundColor Cyan
if (Test-Path $McpDir) { Remove-Item -Recurse -Force $McpDir }
git clone https://github.com/vespo92/chromadblocal-mcp-server.git $McpDir | Out-Null

Write-Host "==> [4/9] Patch MCP server to keep stdout clean" -ForegroundColor Cyan
$IndexJs = Join-Path $McpDir "index.js"
if (-not (Test-Path $IndexJs)) { throw "index.js not found at $IndexJs" }

$lines = Get-Content $IndexJs
$patched = $lines | ForEach-Object {
  if ($_ -match '^\s*console\.log\s*\(') { "//$($_)" } else { $_ }
}
Set-Content -Path $IndexJs -Value $patched -Encoding UTF8

$Dockerfile = Join-Path $McpDir "Dockerfile.mcp"
@"
FROM oven/bun:1
WORKDIR /app
COPY . .
RUN bun install
# IMPORTANT: don't use 'bun run' (it may print banners to stdout)
CMD ["bun","index.js"]
"@ | Set-Content -Path $Dockerfile -Encoding UTF8

Write-Host "==> [5/9] Build MCP server image: chroma-mcp-server:latest" -ForegroundColor Cyan
Push-Location $McpDir
docker build -t chroma-mcp-server:latest -f Dockerfile.mcp . | Out-Host
Pop-Location

Write-Host "==> [6/9] Update Codex config: ~/.codex/config.toml" -ForegroundColor Cyan
$CodexDir = Join-Path $env:USERPROFILE ".codex"
$CodexCfg = Join-Path $CodexDir "config.toml"
if (-not (Test-Path $CodexDir)) { New-Item -ItemType Directory -Path $CodexDir | Out-Null }
if (-not (Test-Path $CodexCfg)) { New-Item -ItemType File -Path $CodexCfg | Out-Null }

$cfgText = Get-Content $CodexCfg -Raw
$cfgText = [regex]::Replace($cfgText, "(?ms)^\[mcp_servers\.chromadb_context\].*?(?=^\[|\z)", "").TrimEnd()

$block = @"
[mcp_servers.chromadb_context]
command = "docker"
args = [
  "run","--rm","-i",
  "--network","$ChromaNetwork",
  "-e","CHROMADB_URL=$ChromaUrlInDocker",
  "-e","REMOTE_CHROMA_URL=$ChromaUrlInDocker",
  "-v","${RepoDockerPath}:/workspace:ro",
  "-w","/workspace",
  "chroma-mcp-server:latest"
]
startup_timeout_sec = 30
tool_timeout_sec = 180
enabled = true

"@

Set-Content -Path $CodexCfg -Value ($cfgText + "`r`n`r`n" + $block) -Encoding UTF8
Write-Host "✅ Codex config updated: $CodexCfg" -ForegroundColor Green

Write-Host "==> [7/9] Validate MCP entry appears in Codex" -ForegroundColor Cyan
codex mcp list | Out-Host

Write-Host ""
Write-Host "==> [8/9] Done" -ForegroundColor Yellow
Write-Host "Chroma (host):   http://localhost:$ChromaHostPort" -ForegroundColor Green
Write-Host "Chroma (docker): $ChromaUrlInDocker" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1) Quit VS Code completely, reopen." -ForegroundColor Yellow
Write-Host "2) Start a NEW Codex chat." -ForegroundColor Yellow
Write-Host "3) Ask Codex to index /workspace and then search." -ForegroundColor Yellow

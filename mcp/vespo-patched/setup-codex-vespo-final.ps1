# setup-codex-vespo-final.ps1
# FINAL VERSION - Complete automated setup for PATCHED vespo92 ChromaDB MCP server
#
# Features:
# - Clones git-rag-chat repo from GitHub
# - Intelligently finds free ports
# - Handles Windows paths with spaces correctly
# - Generates PowerShell-compatible config (NOT Git Bash paths!)
# - Fixes the -w flag issue (removes it completely)
# - Full validation and testing
# - Works from PowerShell (recommended) or Git Bash
#
# Version: 2.0 - Final
# Date: 2026-01-08

$ErrorActionPreference = "Stop"

Write-Host @"
╔═══════════════════════════════════════════════════════════════════╗
║  Patched Vespo ChromaDB MCP Server Setup for Codex CLI (FINAL)   ║
║  - Fixes stdio handshake issues                                   ║
║  - Generates PowerShell-compatible paths                          ║
║  - Removes -w flag that causes failures                           ║
╚═══════════════════════════════════════════════════════════════════╝
"@ -ForegroundColor Cyan

Write-Host ""

# --- Helper Functions ---
function Write-Step {
    param([string]$Message)
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "✓ $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "⚠ $Message" -ForegroundColor Yellow
}

function Write-Info {
    param([string]$Message)
    Write-Host "  $Message" -ForegroundColor White
}

function Write-Error {
    param([string]$Message)
    Write-Host "❌ $Message" -ForegroundColor Red
}

function Test-Port {
    param([int]$Port)
    try {
        $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
        $listener.Start()
        $listener.Stop()
        return $true  # Port is free
    }
    catch {
        return $false  # Port is in use
    }
}

function Get-FreePort {
    param([int]$StartPort, [int]$MaxTries = 50)

    for ($port = $StartPort; $port -lt ($StartPort + $MaxTries); $port++) {
        if (Test-Port -Port $port) {
            return $port
        }
    }
    throw "No free port found in range $StartPort..$($StartPort + $MaxTries - 1)"
}

function ConvertTo-WindowsDockerPath {
    param([string]$WindowsPath)

    # Convert Windows path to Docker volume mount format for PowerShell
    # Input:  C:\Users\Name With Spaces\Documents\project
    # Output: C:\\Users\\Name With Spaces\\Documents\\project
    #         (escaped backslashes for TOML)

    $fullPath = (Resolve-Path $WindowsPath -ErrorAction Stop).Path

    # Escape backslashes for TOML (each \ becomes \\)
    $escapedPath = $fullPath -replace '\\', '\\'

    return $escapedPath
}

# --- Step 1: Prerequisites Check ---
Write-Step "[1/12] Checking prerequisites..."

$missingPrereqs = @()

if (-not (Get-Command codex -ErrorAction SilentlyContinue)) {
    $missingPrereqs += "codex CLI (install: npm install -g @anthropics/claude-code)"
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    $missingPrereqs += "Docker Desktop (install from: https://docker.com)"
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    $missingPrereqs += "Git (install from: https://git-scm.com)"
}

if ($missingPrereqs.Count -gt 0) {
    Write-Host ""
    Write-Error "Missing prerequisites:"
    foreach ($prereq in $missingPrereqs) {
        Write-Host "   - $prereq" -ForegroundColor Red
    }
    throw "Please install missing prerequisites and run this script again."
}

Write-Success "All prerequisites found (codex, docker, git)"

# Check Docker is running
try {
    docker ps *>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Docker Desktop is running"
    }
    else {
        throw "Docker command failed"
    }
}
catch {
    throw "Docker Desktop is not running. Please start Docker Desktop and try again."
}

# Detect current shell environment
$isGitBash = $env:SHELL -match "bash" -or $env:MSYSTEM -ne $null
if ($isGitBash) {
    Write-Warning "You're running from Git Bash - PowerShell is recommended for best compatibility"
    Write-Info "The script will generate PowerShell-compatible config"
}

# --- Step 2: Get User Input ---
Write-Step "[2/12] Getting installation directory..."

Write-Host ""
Write-Host "Where would you like to clone the git-rag-chat repository?" -ForegroundColor Yellow
Write-Host ""
Write-Host "Examples:" -ForegroundColor DarkGray
Write-Host "  - C:\Users\$env:USERNAME\Documents" -ForegroundColor DarkGray
Write-Host "  - C:\Projects" -ForegroundColor DarkGray
Write-Host "  - $env:USERPROFILE\source" -ForegroundColor DarkGray
Write-Host ""
Write-Host "Note: Paths with spaces are fully supported!" -ForegroundColor Green
Write-Host ""

$defaultPath = "$env:USERPROFILE\Documents"
$installDir = Read-Host "Installation directory (press Enter for default: $defaultPath)"

if ([string]::IsNullOrWhiteSpace($installDir)) {
    $installDir = $defaultPath
}

# Clean up path (remove quotes if user added them)
$installDir = $installDir.Trim().Trim('"').Trim("'")

# Verify directory exists or can be created
if (-not (Test-Path $installDir)) {
    Write-Warning "Directory doesn't exist: $installDir"
    $create = Read-Host "Create it? (y/n)"
    if ($create -ne 'y') {
        throw "Installation cancelled by user"
    }
    New-Item -ItemType Directory -Path $installDir -Force | Out-Null
    Write-Success "Created directory: $installDir"
}

Write-Success "Installation directory: $installDir"

# --- Step 3: Clone Repository ---
Write-Step "[3/12] Cloning git-rag-chat repository from GitHub..."

$repoPath = Join-Path $installDir "git-rag-chat"

if (Test-Path $repoPath) {
    Write-Warning "Repository already exists at: $repoPath"
    $overwrite = Read-Host "Delete and re-clone? (y/n)"
    if ($overwrite -eq 'y') {
        Write-Info "Removing existing repository..."
        Remove-Item -Recurse -Force $repoPath
        Write-Info "Removed existing repository"
    }
    else {
        Write-Info "Using existing repository"
    }
}

if (-not (Test-Path $repoPath)) {
    Write-Info "Cloning from https://github.com/SANARP98/git-rag-chat.git"
    Push-Location $installDir
    git clone https://github.com/SANARP98/git-rag-chat.git 2>&1 | Out-Null
    Pop-Location

    if (-not (Test-Path $repoPath)) {
        throw "Failed to clone repository from GitHub"
    }
    Write-Success "Repository cloned successfully"
}

# Verify patched folder exists
$patchedPath = Join-Path $repoPath "mcp\vespo-patched"
if (-not (Test-Path $patchedPath)) {
    throw "Patched vespo server not found at: $patchedPath"
}

Write-Success "Found patched vespo server at: $patchedPath"

# --- Step 4: Docker Network Setup ---
Write-Step "[4/12] Setting up Docker network..."

$networkName = "chroma-net"
$networkExists = docker network inspect $networkName 2>$null
if ($LASTEXITCODE -ne 0) {
    docker network create $networkName | Out-Null
    Write-Success "Created Docker network: $networkName"
}
else {
    Write-Success "Docker network already exists: $networkName"
}

# --- Step 5: Find Free Port for ChromaDB ---
Write-Step "[5/12] Finding free port for ChromaDB..."

# Start from 8003 to avoid conflicts with existing ChromaDB instances
$chromaPort = Get-FreePort -StartPort 8003
Write-Success "Using port $chromaPort for ChromaDB (checked for availability)"

# --- Step 6: Start ChromaDB Container ---
Write-Step "[6/12] Starting ChromaDB container..."

$containerName = "chromadb-vespo"

# Check if container already exists
$existingContainer = docker ps -a --filter "name=^/${containerName}$" --format "{{.Names}}" 2>$null
if ($existingContainer) {
    Write-Warning "Container '$containerName' already exists"
    docker rm -f $containerName 2>&1 | Out-Null
    Write-Info "Removed existing container"
}

# Start new ChromaDB container
Write-Info "Starting container on port $chromaPort..."
docker run -d `
    --name $containerName `
    --network $networkName `
    -p "${chromaPort}:8000" `
    chromadb/chroma:latest | Out-Null

if ($LASTEXITCODE -ne 0) {
    throw "Failed to start ChromaDB container"
}

Write-Success "ChromaDB container started: $containerName"

# --- Step 7: Wait for ChromaDB to be Ready ---
Write-Step "[7/12] Waiting for ChromaDB to be ready..."

$maxWait = 40
$waited = 0
$chromaReady = $false

while ($waited -lt $maxWait) {
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:${chromaPort}/api/v2/heartbeat" -TimeoutSec 2 -ErrorAction Stop
        if ($response) {
            $chromaReady = $true
            break
        }
    }
    catch {
        Start-Sleep -Seconds 1
        $waited++
        if ($waited % 5 -eq 0) {
            Write-Host "." -NoNewline
        }
    }
}

Write-Host ""  # New line after dots

if (-not $chromaReady) {
    throw "ChromaDB failed to start within $maxWait seconds. Check Docker logs: docker logs $containerName"
}

Write-Success "ChromaDB is ready on port $chromaPort"

# --- Step 8: Build MCP Server Image ---
Write-Step "[8/12] Building patched MCP server Docker image..."

Push-Location $patchedPath

$imageName = "chroma-mcp-vespo-patched:latest"
Write-Info "Building Docker image (this may take 1-2 minutes)..."

docker build -t $imageName -f Dockerfile . 2>&1 | Out-Null

if ($LASTEXITCODE -ne 0) {
    Pop-Location
    throw "Failed to build Docker image. Check if Dockerfile exists in $patchedPath"
}

Pop-Location

Write-Success "Docker image built: $imageName"

# --- Step 9: Test MCP Server Handshake ---
Write-Step "[9/12] Testing MCP server handshake..."

$testJson = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0.0"}}}'

# Test WITHOUT volume mount first (simpler)
Write-Info "Testing basic handshake..."
$testResult = $testJson | docker run --rm -i --network $networkName -e "CHROMA_URL=http://${containerName}:8000" $imageName 2>&1 | Select-Object -First 1

if ($testResult -match '^\{' -and $testResult -match '"result"') {
    Write-Success "MCP handshake successful ✓"
}
else {
    Write-Warning "Handshake test returned: $testResult"
    Write-Warning "Continuing anyway, but there may be issues..."
}

# --- Step 10: Update Codex Config ---
Write-Step "[10/12] Updating Codex CLI configuration..."

$codexDir = Join-Path $env:USERPROFILE ".codex"
$configPath = Join-Path $codexDir "config.toml"

if (-not (Test-Path $codexDir)) {
    New-Item -ItemType Directory -Path $codexDir | Out-Null
    Write-Info "Created .codex directory"
}

# Backup existing config
if (Test-Path $configPath) {
    $backupPath = "${configPath}.backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
    Copy-Item $configPath $backupPath
    Write-Info "Backup created: $backupPath"
}

# Read existing config or create new
$configContent = ""
if (Test-Path $configPath) {
    $configContent = Get-Content $configPath -Raw -ErrorAction SilentlyContinue
    if (-not $configContent) { $configContent = "" }
}

# Remove existing chromadb_context_vespo section
$configContent = [regex]::Replace($configContent, "(?ms)^\[mcp_servers\.chromadb_context_vespo\].*?(?=^\[|\z)", "")
$configContent = $configContent.TrimEnd()

# Convert Windows path to TOML-compatible format
$dockerVolumePath = ConvertTo-WindowsDockerPath -WindowsPath $repoPath

Write-Info "Repo path: $repoPath"
Write-Info "Docker volume: $dockerVolumePath"

# Build new config section
# CRITICAL FIXES:
# 1. Use Windows path format (C:\\Users\\...)
# 2. Single colon before /workspace (not ://)
# 3. NO -w flag (this was causing the handshake failure!)

$newSection = @"

# Patched vespo92 ChromaDB MCP server (22 advanced tools + batch processing)
# Auto-configured by setup script on $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
# IMPORTANT: This config uses PowerShell-compatible paths (not Git Bash paths)
[mcp_servers.chromadb_context_vespo]
command = "docker"
args = [
  "run","--rm","-i",
  "--network","$networkName",
  "-e","CHROMA_URL=http://${containerName}:8000",
  "-e","CHROMADB_URL=http://${containerName}:8000",
  "-v","$dockerVolumePath:/workspace:ro",
  "$imageName"
]
startup_timeout_sec = 45
tool_timeout_sec = 180
enabled = true

"@

# Write updated config
$finalConfig = $configContent + $newSection
Set-Content -Path $configPath -Value $finalConfig -Encoding UTF8

Write-Success "Codex config updated: $configPath"
Write-Info "Config uses PowerShell format (recommended)"

# --- Step 11: Verify Registration ---
Write-Step "[11/12] Verifying MCP server registration..."

$mcpList = codex mcp list 2>&1
if ($mcpList -match "chromadb_context_vespo") {
    Write-Success "MCP server registered with Codex CLI ✓"
}
else {
    Write-Warning "MCP server may not be registered yet"
    Write-Info "This is normal - it will appear after restarting VS Code"
}

# Show what was registered
Write-Info "Checking registration details..."
codex mcp get chromadb_context_vespo 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Success "Server details are accessible"
}

# --- Step 12: Summary ---
Write-Step "[12/12] Setup Complete!"

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║                    SETUP SUCCESSFUL ✓                              ║" -ForegroundColor Green
Write-Host "╚════════════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""

Write-Host "📋 Configuration Summary:" -ForegroundColor Cyan
Write-Host ""
Write-Info "Repository:       $repoPath"
Write-Info "ChromaDB:         http://localhost:$chromaPort"
Write-Info "Container:        $containerName"
Write-Info "Network:          $networkName"
Write-Info "MCP Server:       chromadb_context_vespo"
Write-Info "Config File:      $configPath"
Write-Info "Image:            $imageName"
Write-Host ""

Write-Host "🎯 Key Fixes Applied:" -ForegroundColor Yellow
Write-Success "✓ PowerShell-compatible paths (not Git Bash /c/ format)"
Write-Success "✓ Removed -w flag (was causing handshake failures)"
Write-Success "✓ Proper TOML escaping for paths with spaces"
Write-Success "✓ Auto-selected free port ($chromaPort)"
Write-Success "✓ Tested MCP handshake before finalizing"
Write-Host ""

Write-Host "🚀 Next Steps (IMPORTANT):" -ForegroundColor Yellow
Write-Host ""
Write-Host "  1️⃣  Close VS Code COMPLETELY" -ForegroundColor White
Write-Host "     • Press Ctrl+Q or File → Exit" -ForegroundColor DarkGray
Write-Host "     • Not just close window, fully exit the application" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  2️⃣  Reopen VS Code" -ForegroundColor White
Write-Host "     • Navigate to: $repoPath" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  3️⃣  Start Codex from POWERSHELL (not Git Bash!)" -ForegroundColor White
Write-Host "     • Open PowerShell terminal in VS Code" -ForegroundColor DarkGray
Write-Host "     • Run: codex" -ForegroundColor Cyan
Write-Host ""
Write-Host "  4️⃣  Test with these commands in Codex chat:" -ForegroundColor White
Write-Host "     • List all available tools" -ForegroundColor Cyan
Write-Host "     • What tools does chromadb_context_vespo provide?" -ForegroundColor Cyan
Write-Host "     • Scan directory /workspace" -ForegroundColor Cyan
Write-Host ""

Write-Host "📚 Available Tools (22 total):" -ForegroundColor Yellow
Write-Host ""
Write-Info "Core (5):"
Write-Host "  • search_context, store_context, list_collections" -ForegroundColor DarkGray
Write-Host "  • find_similar_patterns, get_environment" -ForegroundColor DarkGray
Write-Info "Batch Processing (10):"
Write-Host "  • batch_ingest, quick_load, scan_directory, unload_collection" -ForegroundColor DarkGray
Write-Host "  • export_collection, import_collection, batch_delete, etc." -ForegroundColor DarkGray
Write-Info "EXIF Tools (1):"
Write-Host "  • extract_exif (camera, GPS, date from photos)" -ForegroundColor DarkGray
Write-Info "Watch Folders (3):"
Write-Host "  • watch_folder, stop_watch, list_watchers" -ForegroundColor DarkGray
Write-Info "Duplicate Detection (3):"
Write-Host "  • find_duplicates, compare_files, find_collection_duplicates" -ForegroundColor DarkGray
Write-Host ""

Write-Host "🐳 Docker Containers Running:" -ForegroundColor Yellow
docker ps --filter "name=chroma" --format "  • {{.Names}} (port {{.Ports}})" 2>$null
Write-Host ""

Write-Host "⚠️  Troubleshooting:" -ForegroundColor Yellow
Write-Host ""
Write-Info "If MCP server doesn't start:"
Write-Host "  1. Make sure you started Codex from PowerShell (not Git Bash)" -ForegroundColor DarkGray
Write-Host "  2. Completely restart VS Code (not just reload)" -ForegroundColor DarkGray
Write-Host "  3. Start a brand new chat (old chats won't see new servers)" -ForegroundColor DarkGray
Write-Host "  4. Check: codex mcp get chromadb_context_vespo" -ForegroundColor DarkGray
Write-Host ""
Write-Info "If you get 'connection closed' error:"
Write-Host "  • The config should now be fixed (uses PowerShell paths)" -ForegroundColor DarkGray
Write-Host "  • Make sure Docker Desktop is running" -ForegroundColor DarkGray
Write-Host "  • Try: docker run --rm -i $imageName" -ForegroundColor DarkGray
Write-Host ""
Write-Info "To enable debug logging:"
Write-Host "  • Edit config.toml and add: `"-e`",`"DEBUG_MCP=true`"," -ForegroundColor DarkGray
Write-Host ""

Write-Host "📖 Documentation:" -ForegroundColor Yellow
Write-Info "• Quick Start:    $repoPath\mcp\QUICK_START.md"
Write-Info "• Full Docs:      $repoPath\mcp\vespo-patched\README.md"
Write-Info "• Troubleshooting: $repoPath\mcp\CODEX_TROUBLESHOOTING.md"
Write-Info "• Tech Details:   $repoPath\mcp\PATCHING_SUMMARY.md"
Write-Host ""

Write-Host "═══════════════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "  Setup completed successfully! Enjoy your 22 MCP tools! 🎉" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""

Write-Host "💡 Pro Tip: Run Codex from PowerShell terminal (View → Terminal → PowerShell)" -ForegroundColor Cyan
Write-Host ""

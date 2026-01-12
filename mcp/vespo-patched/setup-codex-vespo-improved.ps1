# setup-codex-vespo-improved.ps1
# Complete automated setup for PATCHED vespo92 ChromaDB MCP server with Codex CLI
# Features:
# - Clones git-rag-chat repo from GitHub
# - Intelligently finds free ports
# - Handles Windows paths with spaces correctly
# - Updates config.toml with correct paths
# - Full validation and testing

$ErrorActionPreference = "Stop"

Write-Host @"
╔════════════════════════════════════════════════════════════════╗
║  Patched Vespo ChromaDB MCP Server Setup for Codex CLI        ║
║  Fixes stdio handshake issues for ChatGPT Codex CLI           ║
╚════════════════════════════════════════════════════════════════╝
"@ -ForegroundColor Cyan

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

function ConvertTo-DockerPath {
    param([string]$WindowsPath)

    # Convert Windows path to Docker-compatible path
    # C:\Users\... -> /c/Users/...
    $fullPath = (Resolve-Path $WindowsPath -ErrorAction Stop).Path
    $drive = $fullPath.Substring(0, 1).ToLower()
    $restPath = $fullPath.Substring(2) -replace "\\", "/"

    # Escape spaces for Docker
    $dockerPath = "/$drive$restPath"
    return $dockerPath
}

function ConvertTo-TOMLArrayString {
    param([string[]]$Array)

    # Convert array to TOML format with proper escaping
    $escapedItems = $Array | ForEach-Object {
        # Escape backslashes and quotes
        $escaped = $_ -replace '\\', '\\' -replace '"', '\"'
        "`"$escaped`""
    }
    return $escapedItems -join ","
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
    Write-Host "`n❌ Missing prerequisites:" -ForegroundColor Red
    foreach ($prereq in $missingPrereqs) {
        Write-Host "   - $prereq" -ForegroundColor Red
    }
    throw "Please install missing prerequisites and run this script again."
}

Write-Success "All prerequisites found"

# Check Docker is running
try {
    docker ps *>$null
    Write-Success "Docker is running"
}
catch {
    throw "Docker Desktop is not running. Please start Docker Desktop and try again."
}

# --- Step 2: Get User Input ---
Write-Step "[2/12] Getting installation directory..."

Write-Host ""
Write-Host "Where would you like to clone the git-rag-chat repository?" -ForegroundColor Yellow
Write-Host "Examples:" -ForegroundColor DarkGray
Write-Host "  - C:\Users\$env:USERNAME\Documents" -ForegroundColor DarkGray
Write-Host "  - C:\Projects" -ForegroundColor DarkGray
Write-Host "  - $env:USERPROFILE\source" -ForegroundColor DarkGray
Write-Host ""

$defaultPath = "$env:USERPROFILE\Documents"
$installDir = Read-Host "Installation directory (default: $defaultPath)"

if ([string]::IsNullOrWhiteSpace($installDir)) {
    $installDir = $defaultPath
}

# Clean up path (remove quotes if user added them)
$installDir = $installDir.Trim().Trim('"').Trim("'")

# Verify directory exists or can be created
if (-not (Test-Path $installDir)) {
    $create = Read-Host "Directory doesn't exist. Create it? (y/n)"
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
        Remove-Item -Recurse -Force $repoPath
        Write-Info "Removed existing repository"
    }
    else {
        Write-Info "Using existing repository"
    }
}

if (-not (Test-Path $repoPath)) {
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

$chromaPort = Get-FreePort -StartPort 8003
Write-Success "Using port $chromaPort for ChromaDB"

# --- Step 6: Start ChromaDB Container ---
Write-Step "[6/12] Starting ChromaDB container..."

$containerName = "chromadb-vespo"

# Check if container already exists
$existingContainer = docker ps -a --filter "name=^${containerName}$" --format "{{.Names}}" 2>$null
if ($existingContainer) {
    Write-Warning "Container $containerName already exists"
    docker rm -f $containerName 2>&1 | Out-Null
    Write-Info "Removed existing container"
}

# Start new ChromaDB container
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
    }
}

if (-not $chromaReady) {
    throw "ChromaDB failed to start within $maxWait seconds"
}

Write-Success "ChromaDB is ready on port $chromaPort"

# --- Step 8: Build MCP Server Image ---
Write-Step "[8/12] Building patched MCP server Docker image..."

Push-Location $patchedPath

$imageName = "chroma-mcp-vespo-patched:latest"
Write-Info "This may take a minute..."

docker build -t $imageName -f Dockerfile . 2>&1 | Out-Null

if ($LASTEXITCODE -ne 0) {
    Pop-Location
    throw "Failed to build Docker image"
}

Pop-Location

Write-Success "Docker image built: $imageName"

# --- Step 9: Test MCP Server Handshake ---
Write-Step "[9/12] Testing MCP server handshake..."

$testJson = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0.0"}}}'

$testResult = $testJson | docker run --rm -i --network $networkName -e "CHROMA_URL=http://${containerName}:8000" $imageName 2>&1 | Select-Object -First 1

if ($testResult -match '^\{' -and $testResult -match '"result"') {
    Write-Success "MCP handshake successful"
}
else {
    Write-Warning "Handshake test returned: $testResult"
    Write-Warning "Continuing anyway, but there may be issues..."
}

# --- Step 9a: Create Docker Wrapper Script ---
Write-Step "[9a/12] Creating Docker wrapper for dynamic workspace mounting..."

$codexDir = Join-Path $env:USERPROFILE ".codex"
$wrapperScript = Join-Path $codexDir "docker-wrapper.ps1"

if (-not (Test-Path $codexDir)) {
    New-Item -ItemType Directory -Path $codexDir | Out-Null
    Write-Info "Created .codex directory"
}

$wrapperContent = @'
# Docker wrapper for dynamic workspace mounting in Codex MCP
# Automatically mounts current VS Code workspace as /workspace

param(
    [Parameter(ValueFromRemainingArguments)]
    [string[]]$DockerArgs
)

$ErrorActionPreference = "Stop"

# Get current directory from environment
$WorkspaceDir = $env:PWD
if (-not $WorkspaceDir) {
    $WorkspaceDir = (Get-Location).Path
}

# Convert Windows path to Docker path format
function ConvertTo-DockerPath {
    param([string]$Path)
    try {
        $fullPath = (Resolve-Path $Path -ErrorAction Stop).Path
        $drive = $fullPath.Substring(0, 1).ToLower()
        $restPath = $fullPath.Substring(2) -replace "\\", "/"
        return "/$drive$restPath"
    } catch {
        Write-Error "Failed to resolve path: $Path"
        exit 1
    }
}

$DockerPath = ConvertTo-DockerPath -Path $WorkspaceDir

# Find Docker binary
$DockerBin = $null
if (Test-Path "C:\Program Files\Docker\Docker\resources\bin\docker.exe") {
    $DockerBin = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
} elseif (Get-Command docker -ErrorAction SilentlyContinue) {
    $DockerBin = (Get-Command docker).Source
} else {
    Write-Error "Docker command not found"
    exit 1
}

# Parse and modify args
$ModifiedArgs = @()
$SkipNext = $false

for ($i = 0; $i -lt $DockerArgs.Count; $i++) {
    $arg = $DockerArgs[$i]

    if ($SkipNext) {
        # Replace mount path with current workspace
        $ModifiedArgs += "${DockerPath}:/workspace:ro"
        $SkipNext = $false
    }
    elseif ($arg -eq "-v") {
        $ModifiedArgs += $arg
        $SkipNext = $true
    }
    elseif ($arg -like "*:/workspace:ro" -or $arg -like "*://workspace:ro") {
        # Replace inline mount (handle both : and :: formats)
        $ModifiedArgs += "${DockerPath}:/workspace:ro"
    }
    else {
        $ModifiedArgs += $arg
    }
}

# Execute real docker
& $DockerBin @ModifiedArgs
exit $LASTEXITCODE
'@

Set-Content -Path $wrapperScript -Value $wrapperContent -Encoding UTF8
Write-Success "Docker wrapper created: $wrapperScript"
Write-Info "Wrapper will dynamically mount current workspace"

# --- Step 10: Update Codex Config ---
Write-Step "[10/12] Updating Codex CLI configuration..."

$configPath = Join-Path $codexDir "config.toml"

# Read existing config or create new
$configContent = ""
if (Test-Path $configPath) {
    $configContent = Get-Content $configPath -Raw -ErrorAction SilentlyContinue
    if (-not $configContent) { $configContent = "" }
}

# Remove existing chromadb_context_vespo section
$configContent = [regex]::Replace($configContent, "(?ms)^\[mcp_servers\.chromadb_context_vespo\].*?(?=^\[|\z)", "")
$configContent = $configContent.TrimEnd()

# Escape backslashes in wrapper path for TOML
$wrapperPathEscaped = $wrapperScript -replace '\\', '\\\\'

# Build new config section with wrapper script
$newSection = @"

# Patched vespo92 ChromaDB MCP server (22 advanced tools + batch processing)
# Auto-configured by setup script on $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
# Uses dynamic workspace mounting - automatically mounts current VS Code workspace
[mcp_servers.chromadb_context_vespo]
command = "$wrapperPathEscaped"
args = [
  "run","--rm","-i",
  "--network","$networkName",
  "-e","CHROMA_URL=http://${containerName}:8000",
  "-e","CHROMADB_URL=http://${containerName}:8000",
  "-v","PLACEHOLDER:/workspace:ro",
  "$imageName"
]
env_vars = ["PWD"]
startup_timeout_sec = 45
tool_timeout_sec = 180
enabled = true

"@

# Write updated config
$finalConfig = $configContent + $newSection
Set-Content -Path $configPath -Value $finalConfig -Encoding UTF8

Write-Success "Codex config updated: $configPath"

# --- Step 11: Verify Registration ---
Write-Step "[11/12] Verifying MCP server registration..."

$mcpList = codex mcp list 2>&1
if ($mcpList -match "chromadb_context_vespo") {
    Write-Success "MCP server registered with Codex CLI"
}
else {
    Write-Warning "MCP server may not be registered yet"
    Write-Info "This is normal - it will appear after restarting VS Code"
}

# --- Step 12: Summary ---
Write-Step "[12/12] Setup Complete!"

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║                    SETUP SUCCESSFUL                            ║" -ForegroundColor Green
Write-Host "╚════════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""

Write-Host "Configuration Summary:" -ForegroundColor Cyan
Write-Info "Repository:       $repoPath"
Write-Info "ChromaDB:         http://localhost:$chromaPort"
Write-Info "Container:        $containerName"
Write-Info "Network:          $networkName"
Write-Info "MCP Server:       chromadb_context_vespo"
Write-Info "Config File:      $configPath"
Write-Info "Docker Wrapper:   $wrapperScript"

Write-Host ""
Write-Host "✓ Dynamic Workspace Mounting Enabled" -ForegroundColor Green
Write-Info "The MCP server will automatically mount your current VS Code workspace"
Write-Info "No reconfiguration needed when switching between projects!"

Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host ""
Write-Host "  1. Close VS Code COMPLETELY (Ctrl+Q or File → Exit)" -ForegroundColor White
Write-Host "     - Not just close window, fully exit the application" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  2. Reopen VS Code and navigate to your project" -ForegroundColor White
Write-Host ""
Write-Host "  3. Start a NEW Codex chat (Ctrl+Shift+P → 'Codex: New Chat')" -ForegroundColor White
Write-Host ""
Write-Host "  4. Test with these commands:" -ForegroundColor White
Write-Host "     • List all MCP servers" -ForegroundColor Cyan
Write-Host "     • List all tools from chromadb_context_vespo" -ForegroundColor Cyan
Write-Host "     • Scan directory /workspace" -ForegroundColor Cyan
Write-Host ""

Write-Host "Available Tools (22 total):" -ForegroundColor Yellow
Write-Info "• Core: search_context, store_context, list_collections, etc."
Write-Info "• Batch Processing: batch_ingest, quick_load, scan_directory, etc."
Write-Info "• EXIF Tools: extract_exif (camera, GPS, date from photos)"
Write-Info "• Watch Folders: watch_folder, stop_watch, list_watchers"
Write-Info "• Duplicate Detection: find_duplicates, compare_files"

Write-Host ""
Write-Host "Docker Containers Running:" -ForegroundColor Yellow
docker ps --filter "name=chroma" --format "  • {{.Names}} (port {{.Ports}})" 2>$null

Write-Host ""
Write-Host "Troubleshooting:" -ForegroundColor Yellow
Write-Info "If MCP server doesn't appear:"
Write-Info "  1. Make sure you COMPLETELY restarted VS Code"
Write-Info "  2. Start a brand NEW chat (old chats won't see it)"
Write-Info "  3. Check logs: codex mcp logs chromadb_context_vespo"
Write-Host ""
Write-Info "To enable debug logging, add to config.toml args:"
Write-Info '  "-e","DEBUG_MCP=true",'
Write-Host ""

Write-Host "Documentation:" -ForegroundColor Yellow
Write-Info "• Quick Start: $repoPath\mcp\QUICK_START.md"
Write-Info "• Full Docs:   $repoPath\mcp\vespo-patched\README.md"
Write-Info "• Tech Details: $repoPath\mcp\PATCHING_SUMMARY.md"

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "  Setup completed successfully! Enjoy your 22 MCP tools! 🎉" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""

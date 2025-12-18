# Git RAG Chat - Deployment and Testing Script (PowerShell)
# This script builds, deploys, and tests the application on Windows

$ErrorActionPreference = "Stop"

Write-Host "==================================" -ForegroundColor Cyan
Write-Host "Git RAG Chat - Deploy & Test" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""

function Print-Step {
    param([string]$Message)
    Write-Host "[STEP] $Message" -ForegroundColor Green
}

function Print-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

function Print-Warning {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
}

# Step 1: Check prerequisites
Print-Step "Checking prerequisites..."

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Print-Error "Docker is not installed. Please install Docker Desktop first."
    exit 1
}

if (-not (Get-Command docker-compose -ErrorAction SilentlyContinue)) {
    Print-Error "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
}

$dockerVersion = docker --version
$composeVersion = docker-compose --version
Print-Step "Docker version: $dockerVersion"
Print-Step "Docker Compose version: $composeVersion"

# Step 2: Check environment variables
Print-Step "Checking environment variables..."
if (-not (Test-Path .env)) {
    Print-Warning ".env file not found. Creating from .env.example..."
    if (Test-Path .env.example) {
        Copy-Item .env.example .env
        Print-Warning "Please edit .env file with your configuration"
    } else {
        Print-Error ".env.example not found. Please create .env file manually."
        exit 1
    }
}

# Check for OpenAI API key if using OpenAI embeddings
$envContent = Get-Content .env -Raw
if ($envContent -match "EMBEDDING_PROVIDER=openai") {
    if ($envContent -notmatch "OPENAI_API_KEY=sk-") {
        Print-Warning "OPENAI_API_KEY not set properly in .env. Using local embeddings instead."
    }
}

# Step 3: Stop existing containers
Print-Step "Stopping existing containers..."
docker-compose down 2>$null

# Step 4: Build containers
Print-Step "Building Docker containers (this may take a few minutes)..."
docker-compose build --no-cache

if ($LASTEXITCODE -ne 0) {
    Print-Error "Docker build failed"
    exit 1
}

# Step 5: Start services
Print-Step "Starting services..."
docker-compose up -d chromadb rag-pipeline web-ui

# Wait for services to be healthy
Print-Step "Waiting for services to be ready..."
Start-Sleep -Seconds 10

# Check ChromaDB
Print-Step "Checking ChromaDB health..."
$maxRetries = 30
$retryCount = 0
$chromaReady = $false

while ($retryCount -lt $maxRetries) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/heartbeat" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            Print-Step "ChromaDB is healthy"
            $chromaReady = $true
            break
        }
    } catch {
        # Continue trying
    }
    $retryCount++
    Write-Host "Waiting for ChromaDB... ($retryCount/$maxRetries)"
    Start-Sleep -Seconds 2
}

if (-not $chromaReady) {
    Print-Error "ChromaDB failed to start"
    docker-compose logs chromadb
    exit 1
}

# Check RAG Pipeline
Print-Step "Checking RAG Pipeline health..."
$retryCount = 0
$ragReady = $false

while ($retryCount -lt $maxRetries) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8001/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            Print-Step "RAG Pipeline is healthy"
            $ragReady = $true
            break
        }
    } catch {
        # Continue trying
    }
    $retryCount++
    Write-Host "Waiting for RAG Pipeline... ($retryCount/$maxRetries)"
    Start-Sleep -Seconds 2
}

if (-not $ragReady) {
    Print-Error "RAG Pipeline failed to start"
    docker-compose logs rag-pipeline
    exit 1
}

# Check Web UI
Print-Step "Checking Web UI health..."
$retryCount = 0
$uiReady = $false

while ($retryCount -lt $maxRetries) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:7860" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            Print-Step "Web UI is healthy"
            $uiReady = $true
            break
        }
    } catch {
        # Continue trying
    }
    $retryCount++
    Write-Host "Waiting for Web UI... ($retryCount/$maxRetries)"
    Start-Sleep -Seconds 2
}

if (-not $uiReady) {
    Print-Warning "Web UI may not be fully ready yet"
}

# Step 6: Run health checks
Print-Step "Running health checks..."

Write-Host ""
Write-Host "=== ChromaDB Health ===" -ForegroundColor Cyan
try {
    $health = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/heartbeat"
    $health | ConvertTo-Json
} catch {
    Write-Host "N/A"
}

Write-Host ""
Write-Host "=== RAG Pipeline Health ===" -ForegroundColor Cyan
try {
    $health = Invoke-RestMethod -Uri "http://localhost:8001/health"
    $health | ConvertTo-Json
} catch {
    Write-Host "N/A"
}

Write-Host ""
Print-Step "All services are running!"
Write-Host ""
Write-Host "Access points:" -ForegroundColor Cyan
Write-Host "  - Web UI: http://localhost:7860" -ForegroundColor Yellow
Write-Host "  - RAG API: http://localhost:8001" -ForegroundColor Yellow
Write-Host "  - ChromaDB: http://localhost:8000" -ForegroundColor Yellow
Write-Host ""

# Step 7: Show logs
Print-Step "Showing recent logs (last 50 lines)..."
Write-Host ""
Write-Host "=== ChromaDB Logs ===" -ForegroundColor Cyan
docker-compose logs --tail=50 chromadb
Write-Host ""
Write-Host "=== RAG Pipeline Logs ===" -ForegroundColor Cyan
docker-compose logs --tail=50 rag-pipeline
Write-Host ""

# Step 8: Provide next steps
Write-Host ""
Write-Host "==================================" -ForegroundColor Cyan
Write-Host "Deployment Complete!" -ForegroundColor Green
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Open Web UI: http://localhost:7860"
Write-Host "  2. Add a repository"
Write-Host "  3. Start indexing"
Write-Host ""
Write-Host "Useful commands:" -ForegroundColor Yellow
Write-Host "  - View logs: docker-compose logs -f"
Write-Host "  - Stop services: docker-compose down"
Write-Host "  - Restart: docker-compose restart"
Write-Host "  - Check status: docker-compose ps"
Write-Host ""

# Open browser automatically
$openBrowser = Read-Host "Open Web UI in browser? (Y/n)"
if ($openBrowser -ne "n" -and $openBrowser -ne "N") {
    Start-Process "http://localhost:7860"
}

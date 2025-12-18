#!/bin/bash

# Git RAG Chat - Deployment and Testing Script
# This script builds, deploys, and tests the application

set -e  # Exit on error

echo "=================================="
echo "Git RAG Chat - Deploy & Test"
echo "=================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
print_step() {
    echo -e "${GREEN}[STEP]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Step 1: Check prerequisites
print_step "Checking prerequisites..."
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    print_error "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

print_step "Docker version: $(docker --version)"
print_step "Docker Compose version: $(docker-compose --version)"

# Step 2: Check environment variables
print_step "Checking environment variables..."
if [ ! -f .env ]; then
    print_warning ".env file not found. Creating from .env.example..."
    if [ -f .env.example ]; then
        cp .env.example .env
        print_warning "Please edit .env file with your configuration"
    else
        print_error ".env.example not found. Please create .env file manually."
        exit 1
    fi
fi

# Check for OpenAI API key if using OpenAI embeddings
EMBEDDING_PROVIDER=$(grep EMBEDDING_PROVIDER .env | cut -d '=' -f2 || echo "local")
if [ "$EMBEDDING_PROVIDER" == "openai" ]; then
    OPENAI_KEY=$(grep OPENAI_API_KEY .env | cut -d '=' -f2 || echo "")
    if [ -z "$OPENAI_KEY" ] || [ "$OPENAI_KEY" == "" ]; then
        print_warning "OPENAI_API_KEY not set in .env. Using local embeddings instead."
    fi
fi

# Step 3: Stop existing containers
print_step "Stopping existing containers..."
docker-compose down || true

# Step 4: Build containers
print_step "Building Docker containers..."
docker-compose build --no-cache

if [ $? -ne 0 ]; then
    print_error "Docker build failed"
    exit 1
fi

# Step 5: Start services
print_step "Starting services..."
docker-compose up -d chromadb rag-pipeline web-ui

# Wait for services to be healthy
print_step "Waiting for services to be ready..."
sleep 10

# Check ChromaDB
print_step "Checking ChromaDB health..."
MAX_RETRIES=30
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s http://localhost:8000/api/v1/heartbeat > /dev/null 2>&1; then
        print_step "ChromaDB is healthy"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "Waiting for ChromaDB... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    print_error "ChromaDB failed to start"
    docker-compose logs chromadb
    exit 1
fi

# Check RAG Pipeline
print_step "Checking RAG Pipeline health..."
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s http://localhost:8001/health > /dev/null 2>&1; then
        print_step "RAG Pipeline is healthy"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "Waiting for RAG Pipeline... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    print_error "RAG Pipeline failed to start"
    docker-compose logs rag-pipeline
    exit 1
fi

# Check Web UI
print_step "Checking Web UI health..."
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s http://localhost:7860 > /dev/null 2>&1; then
        print_step "Web UI is healthy"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "Waiting for Web UI... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    print_warning "Web UI may not be fully ready yet"
fi

# Step 6: Run health checks
print_step "Running health checks..."

echo ""
echo "=== ChromaDB Health ==="
curl -s http://localhost:8000/api/v1/heartbeat | python3 -m json.tool || echo "N/A"

echo ""
echo "=== RAG Pipeline Health ==="
curl -s http://localhost:8001/health | python3 -m json.tool || echo "N/A"

echo ""
print_step "All services are running!"
echo ""
echo "Access points:"
echo "  - Web UI: http://localhost:7860"
echo "  - RAG API: http://localhost:8001"
echo "  - ChromaDB: http://localhost:8000"
echo ""

# Step 7: Show logs
print_step "Showing recent logs (last 50 lines)..."
echo ""
echo "=== ChromaDB Logs ==="
docker-compose logs --tail=50 chromadb
echo ""
echo "=== RAG Pipeline Logs ==="
docker-compose logs --tail=50 rag-pipeline
echo ""

# Step 8: Provide next steps
echo ""
echo "=================================="
echo "Deployment Complete!"
echo "=================================="
echo ""
echo "Next steps:"
echo "  1. Open Web UI: http://localhost:7860"
echo "  2. Add a repository"
echo "  3. Start indexing"
echo ""
echo "Useful commands:"
echo "  - View logs: docker-compose logs -f"
echo "  - Stop services: docker-compose down"
echo "  - Restart: docker-compose restart"
echo "  - Check status: docker-compose ps"
echo ""

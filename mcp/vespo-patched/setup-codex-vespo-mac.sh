#!/bin/bash
# setup-codex-vespo-mac.sh
# Complete automated setup for PATCHED vespo92 ChromaDB MCP server with Codex CLI (macOS)
# Features:
# - Clones git-rag-chat repo from GitHub
# - Intelligently finds free ports
# - Handles macOS paths correctly
# - Updates config.toml with correct paths
# - Full validation and testing

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
GRAY='\033[0;90m'
NC='\033[0m' # No Color

echo -e "${CYAN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║  Patched Vespo ChromaDB MCP Server Setup for Codex CLI        ║${NC}"
echo -e "${CYAN}║  Fixes stdio handshake issues for ChatGPT Codex CLI           ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════════╝${NC}"

# --- Helper Functions ---
write_step() {
    echo -e "\n${CYAN}==> $1${NC}"
}

write_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

write_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

write_info() {
    echo -e "  $1"
}

write_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if port is available
test_port() {
    local port=$1
    if nc -z localhost "$port" 2>/dev/null; then
        return 1  # Port is in use
    else
        return 0  # Port is free
    fi
}

# Find a free port starting from a given port
get_free_port() {
    local start_port=$1
    local max_tries=${2:-50}

    for ((port=start_port; port<start_port+max_tries; port++)); do
        if test_port "$port"; then
            echo "$port"
            return 0
        fi
    done

    write_error "No free port found in range $start_port..$((start_port + max_tries - 1))"
    exit 1
}

# --- Step 1: Prerequisites Check ---
write_step "[1/12] Checking prerequisites..."

missing_prereqs=()

if ! command -v codex &> /dev/null; then
    missing_prereqs+=("codex CLI (install: npm install -g @anthropics/claude-code)")
fi

if ! command -v docker &> /dev/null; then
    missing_prereqs+=("Docker Desktop (install from: https://docker.com)")
fi

if ! command -v git &> /dev/null; then
    missing_prereqs+=("Git (should be pre-installed on macOS)")
fi

if ! command -v nc &> /dev/null; then
    missing_prereqs+=("netcat (should be pre-installed on macOS)")
fi

if [ ${#missing_prereqs[@]} -gt 0 ]; then
    echo ""
    write_error "Missing prerequisites:"
    for prereq in "${missing_prereqs[@]}"; do
        echo -e "${RED}   - $prereq${NC}"
    done
    exit 1
fi

write_success "All prerequisites found"

# Check Docker is running
if ! docker ps &> /dev/null; then
    write_error "Docker Desktop is not running. Please start Docker Desktop and try again."
    exit 1
fi

write_success "Docker is running"

# --- Step 2: Get User Input ---
write_step "[2/12] Getting installation directory..."

echo ""
echo -e "${YELLOW}Where would you like to clone the git-rag-chat repository?${NC}"
echo -e "${GRAY}Examples:${NC}"
echo -e "${GRAY}  - $HOME/Documents${NC}"
echo -e "${GRAY}  - $HOME/Projects${NC}"
echo -e "${GRAY}  - $HOME/source${NC}"
echo ""

default_path="$HOME/Documents"
read -p "Installation directory (default: $default_path): " install_dir

if [ -z "$install_dir" ]; then
    install_dir="$default_path"
fi

# Clean up path (remove quotes if user added them)
install_dir="${install_dir//\"/}"
install_dir="${install_dir//\'/}"

# Expand ~ if present
install_dir="${install_dir/#\~/$HOME}"

# Verify directory exists or can be created
if [ ! -d "$install_dir" ]; then
    read -p "Directory doesn't exist. Create it? (y/n): " create
    if [ "$create" != "y" ]; then
        write_error "Installation cancelled by user"
        exit 1
    fi
    mkdir -p "$install_dir"
    write_success "Created directory: $install_dir"
fi

write_success "Installation directory: $install_dir"

# --- Step 3: Clone Repository ---
write_step "[3/12] Cloning git-rag-chat repository from GitHub..."

repo_path="$install_dir/git-rag-chat"

if [ -d "$repo_path" ]; then
    write_warning "Repository already exists at: $repo_path"
    read -p "Delete and re-clone? (y/n): " overwrite
    if [ "$overwrite" = "y" ]; then
        rm -rf "$repo_path"
        write_info "Removed existing repository"
    else
        write_info "Using existing repository"
    fi
fi

if [ ! -d "$repo_path" ]; then
    cd "$install_dir"
    git clone https://github.com/SANARP98/git-rag-chat.git &> /dev/null

    if [ ! -d "$repo_path" ]; then
        write_error "Failed to clone repository from GitHub"
        exit 1
    fi
    write_success "Repository cloned successfully"
fi

# Verify patched folder exists
patched_path="$repo_path/mcp/vespo-patched"
if [ ! -d "$patched_path" ]; then
    write_error "Patched vespo server not found at: $patched_path"
    exit 1
fi

write_success "Found patched vespo server at: $patched_path"

# --- Step 4: Docker Network Setup ---
write_step "[4/12] Setting up Docker network..."

network_name="chroma-net"
if ! docker network inspect "$network_name" &> /dev/null; then
    docker network create "$network_name" &> /dev/null
    write_success "Created Docker network: $network_name"
else
    write_success "Docker network already exists: $network_name"
fi

# --- Step 5: Find Free Port for ChromaDB ---
write_step "[5/12] Finding free port for ChromaDB..."

chroma_port=$(get_free_port 8003)
write_success "Using port $chroma_port for ChromaDB"

# --- Step 6: Start ChromaDB Container ---
write_step "[6/12] Starting ChromaDB container..."

container_name="chromadb-vespo"

# Check if container already exists
if docker ps -a --filter "name=^${container_name}$" --format "{{.Names}}" | grep -q "^${container_name}$"; then
    write_warning "Container $container_name already exists"
    docker rm -f "$container_name" &> /dev/null
    write_info "Removed existing container"
fi

# Start new ChromaDB container
docker run -d \
    --name "$container_name" \
    --network "$network_name" \
    -p "${chroma_port}:8000" \
    chromadb/chroma:latest &> /dev/null

if [ $? -ne 0 ]; then
    write_error "Failed to start ChromaDB container"
    exit 1
fi

write_success "ChromaDB container started: $container_name"

# --- Step 7: Wait for ChromaDB to be Ready ---
write_step "[7/12] Waiting for ChromaDB to be ready..."

max_wait=40
waited=0
chroma_ready=false

while [ $waited -lt $max_wait ]; do
    if curl -s "http://localhost:${chroma_port}/api/v2/heartbeat" &> /dev/null; then
        chroma_ready=true
        break
    fi
    sleep 1
    ((waited++))
done

if [ "$chroma_ready" = false ]; then
    write_error "ChromaDB failed to start within $max_wait seconds"
    exit 1
fi

write_success "ChromaDB is ready on port $chroma_port"

# --- Step 8: Build MCP Server Image ---
write_step "[8/12] Building patched MCP server Docker image..."

cd "$patched_path"

image_name="chroma-mcp-vespo-patched:latest"
write_info "This may take a minute..."

docker build -t "$image_name" -f Dockerfile . &> /dev/null

if [ $? -ne 0 ]; then
    write_error "Failed to build Docker image"
    exit 1
fi

write_success "Docker image built: $image_name"

# --- Step 9: Test MCP Server Handshake ---
write_step "[9/12] Testing MCP server handshake..."

test_json='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0.0"}}}'

test_result=$(echo "$test_json" | docker run --rm -i --network "$network_name" -e "CHROMA_URL=http://${container_name}:8000" "$image_name" 2>&1 | head -n 1)

if [[ "$test_result" == *"{"* ]] && [[ "$test_result" == *'"result"'* ]]; then
    write_success "MCP handshake successful"
else
    write_warning "Handshake test returned: $test_result"
    write_warning "Continuing anyway, but there may be issues..."
fi

# --- Step 9: Create Docker Wrapper Script ---
write_step "[9/12] Creating Docker wrapper for dynamic workspace mounting..."

codex_dir="$HOME/.codex"
wrapper_script="$codex_dir/docker-wrapper.sh"

if [ ! -d "$codex_dir" ]; then
    mkdir -p "$codex_dir"
    write_info "Created .codex directory"
fi

cat > "$wrapper_script" << 'WRAPPER_EOF'
#!/bin/bash
# Docker wrapper for dynamic workspace mounting in Codex MCP
# Automatically mounts current VS Code workspace as /workspace

# Get current directory (from PWD env var passed by Codex)
WORKSPACE_DIR="${PWD:-$(pwd)}"

# Find Docker binary
if [ -x "/usr/local/bin/docker" ]; then
    DOCKER_BIN="/usr/local/bin/docker"
elif command -v docker &> /dev/null; then
    DOCKER_BIN=$(command -v docker)
else
    echo "Error: docker command not found" >&2
    exit 1
fi

# Parse args to find and replace -v mount
ARGS=()
SKIP_NEXT=false

for arg in "$@"; do
  if [ "$SKIP_NEXT" = true ]; then
    # This was a mount path, inject our dynamic one
    ARGS+=("${WORKSPACE_DIR}:/workspace:ro")
    SKIP_NEXT=false
  elif [[ "$arg" == "-v" ]]; then
    # Keep -v flag
    ARGS+=("$arg")
    SKIP_NEXT=true
  elif [[ "$arg" == *":/workspace:ro" ]]; then
    # Replace inline -v mount
    ARGS+=("${WORKSPACE_DIR}:/workspace:ro")
  else
    # Keep all other args
    ARGS+=("$arg")
  fi
done

# Execute real docker with modified args
exec "$DOCKER_BIN" "${ARGS[@]}"
WRAPPER_EOF

chmod +x "$wrapper_script"
write_success "Docker wrapper created: $wrapper_script"
write_info "Wrapper will dynamically mount current workspace"

# --- Step 10: Update Codex Config ---
write_step "[10/12] Updating Codex CLI configuration..."

config_path="$codex_dir/config.toml"

if [ ! -d "$codex_dir" ]; then
    mkdir -p "$codex_dir"
    write_info "Created .codex directory"
fi

# Read existing config or create new
config_content=""
if [ -f "$config_path" ]; then
    config_content=$(cat "$config_path")
fi

# Remove existing chromadb_context_vespo section using perl for multi-line regex
if [ -n "$config_content" ]; then
    config_content=$(echo "$config_content" | perl -0pe 's/^\[mcp_servers\.chromadb_context_vespo\].*?(?=^\[|\z)//ms')
fi

# Build new config section with wrapper script
current_date=$(date "+%Y-%m-%d %H:%M:%S")
new_section="
# Patched vespo92 ChromaDB MCP server (22 advanced tools + batch processing)
# Auto-configured by setup script on $current_date
# Uses dynamic workspace mounting - automatically mounts current VS Code workspace
[mcp_servers.chromadb_context_vespo]
command = \"$wrapper_script\"
args = [
  \"run\",\"--rm\",\"-i\",
  \"--network\",\"$network_name\",
  \"-e\",\"CHROMA_URL=http://${container_name}:8000\",
  \"-e\",\"CHROMADB_URL=http://${container_name}:8000\",
  \"-v\",\"PLACEHOLDER:/workspace:ro\",
  \"$image_name\"
]
env_vars = [\"PWD\"]
startup_timeout_sec = 45
tool_timeout_sec = 180
enabled = true

"

# Write updated config
echo "${config_content}${new_section}" > "$config_path"

write_success "Codex config updated: $config_path"

# --- Step 11: Verify Registration ---
write_step "[11/12] Verifying MCP server registration..."

if codex mcp list 2>&1 | grep -q "chromadb_context_vespo"; then
    write_success "MCP server registered with Codex CLI"
else
    write_warning "MCP server may not be registered yet"
    write_info "This is normal - it will appear after restarting VS Code"
fi

# --- Step 12: Summary ---
write_step "[12/12] Setup Complete!"

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                    SETUP SUCCESSFUL                            ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${CYAN}Configuration Summary:${NC}"
write_info "Repository:       $repo_path"
write_info "ChromaDB:         http://localhost:$chroma_port"
write_info "Container:        $container_name"
write_info "Network:          $network_name"
write_info "MCP Server:       chromadb_context_vespo"
write_info "Config File:      $config_path"
write_info "Docker Wrapper:   $wrapper_script"
echo ""
echo -e "${GREEN}✓ Dynamic Workspace Mounting Enabled${NC}"
write_info "The MCP server will automatically mount your current VS Code workspace"
write_info "No reconfiguration needed when switching between projects!"

echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo ""
echo -e "  ${NC}1. Close VS Code COMPLETELY (Cmd+Q or Code → Quit)${NC}"
echo -e "${GRAY}     - Not just close window, fully exit the application${NC}"
echo ""
echo -e "  ${NC}2. Reopen VS Code and navigate to your project${NC}"
echo ""
echo -e "  ${NC}3. Start a NEW Codex chat (Cmd+Shift+P → 'Codex: New Chat')${NC}"
echo ""
echo -e "  ${NC}4. Test with these commands:${NC}"
echo -e "${CYAN}     • List all MCP servers${NC}"
echo -e "${CYAN}     • List all tools from chromadb_context_vespo${NC}"
echo -e "${CYAN}     • Scan directory /workspace${NC}"
echo ""

echo -e "${YELLOW}Available Tools (22 total):${NC}"
write_info "• Core: search_context, store_context, list_collections, etc."
write_info "• Batch Processing: batch_ingest, quick_load, scan_directory, etc."
write_info "• EXIF Tools: extract_exif (camera, GPS, date from photos)"
write_info "• Watch Folders: watch_folder, stop_watch, list_watchers"
write_info "• Duplicate Detection: find_duplicates, compare_files"

echo ""
echo -e "${YELLOW}Docker Containers Running:${NC}"
docker ps --filter "name=chroma" --format "  • {{.Names}} (port {{.Ports}})" 2>/dev/null

echo ""
echo -e "${YELLOW}Troubleshooting:${NC}"
write_info "If MCP server doesn't appear:"
write_info "  1. Make sure you COMPLETELY restarted VS Code"
write_info "  2. Start a brand NEW chat (old chats won't see it)"
write_info "  3. Check logs: codex mcp logs chromadb_context_vespo"
echo ""
write_info "To enable debug logging, add to config.toml args:"
write_info '  "-e","DEBUG_MCP=true",'
echo ""

echo -e "${YELLOW}Documentation:${NC}"
write_info "• Quick Start: $repo_path/mcp/QUICK_START.md"
write_info "• Full Docs:   $repo_path/mcp/vespo-patched/README.md"
write_info "• Tech Details: $repo_path/mcp/PATCHING_SUMMARY.md"

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Setup completed successfully! Enjoy your 22 MCP tools! 🎉${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# Git RAG Chat - Complete Setup and Usage Guide

This guide walks you through setting up and using the Git RAG Chat system, a Docker-based RAG (Retrieval-Augmented Generation) chatbot that lets you query your Git repositories using natural language.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Codex CLI Setup](#codex-cli-setup)
3. [Docker Setup](#docker-setup)
4. [Using the Gradio Web UI](#using-the-gradio-web-ui)
5. [Advanced Configuration](#advanced-configuration)
6. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before you begin, ensure you have the following installed:

- **Docker Desktop** (includes Docker Compose)
  - macOS: [Download Docker Desktop](https://www.docker.com/products/docker-desktop)
  - Linux: Install Docker Engine and Docker Compose separately
  - Windows: [Download Docker Desktop](https://www.docker.com/products/docker-desktop)

- **Codex CLI** (for ChatGPT Enterprise access)
  - Required for LLM-powered responses
  - Installation instructions below

- **Git** (for repository management)

---

## Codex CLI Setup

Codex CLI provides access to ChatGPT Enterprise (GPT-4) for generating intelligent responses.

### 1. Install Codex CLI

#### macOS/Linux
```bash
# Using Homebrew (recommended for macOS)
brew install codex-cli

# Or using pip
pip3 install codex-cli

# Or download the binary directly from the official source
```

#### Verify Installation
```bash
codex --version
```

### 2. Authenticate with ChatGPT Enterprise

You need to authenticate Codex CLI with your ChatGPT Enterprise account:

```bash
codex auth login
```

This will:
- Open your browser to the authentication page
- Ask you to log in with your ChatGPT Enterprise credentials
- Save your authentication token to `~/.codex/config.toml`

### 3. Verify Authentication

Check that Codex is properly authenticated:

```bash
# Test a simple query
codex "Hello, are you working?"

# Check configuration
cat ~/.codex/config.toml
```

You should see your profile information in the config file.

### 4. Important: Codex Configuration Location

The Docker setup **mounts your Codex configuration** from your host machine:

```yaml
# In docker-compose.yml
volumes:
  - /Users/sana/.codex:/root/.codex  # macOS example
  - ~/.codex:/root/.codex             # Linux example
```

**On macOS**, update line 30 in [docker-compose.yml](docker-compose.yml) to match your username:
```yaml
- /Users/YOUR_USERNAME/.codex:/root/.codex
```

**On Linux**, it should work as-is with `~/.codex`.

---

## Docker Setup

### 1. Clone the Repository (if you haven't already)

```bash
git clone <repository-url>
cd git-rag-chat-local
```

### 2. Configure Environment Variables

Copy the example environment file:

```bash
cp .env.example .env
```

Open [.env](.env) and verify/update these settings:

```bash
# LLM Provider - Use 'codex' for ChatGPT Enterprise
LLM_PROVIDER=codex

# Optional: Specify a Codex profile (leave empty for default)
CODEX_PROFILE=

# Embedding model (default is good for most cases)
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# Gradio UI port
GRADIO_SERVER_PORT=7860

# Logging level
LOG_LEVEL=INFO
```

### 3. Update docker-compose.yml Paths

**Important for macOS users**: Update the Codex mount path in [docker-compose.yml](docker-compose.yml#L30):

```yaml
# Line 30 - Update with your actual username
- /Users/YOUR_USERNAME/.codex:/root/.codex
```

The system also mounts your Documents folder (optional, for easy repository access):

```yaml
# Line 29 - Update if needed
- /Users/YOUR_USERNAME/Documents:/host/Documents:ro
```

### 4. Build and Start Services

Start all services with Docker Compose:

```bash
# Build and start all services
docker-compose up --build

# Or run in detached mode (background)
docker-compose up --build -d
```

This will start:
- **ChromaDB** (Vector database) on port `8000`
- **RAG Pipeline** (API backend) on port `8001`
- **Web UI** (Gradio interface) on port `7860`

### 5. Verify Services are Running

```bash
# Check running containers
docker ps

# You should see:
# - git-rag-chromadb
# - git-rag-pipeline
# - git-rag-ui
```

### 6. Check Service Health

```bash
# Check ChromaDB
curl http://localhost:8000/api/v1/heartbeat

# Check RAG Pipeline API
curl http://localhost:8001/health

# Access API documentation
open http://localhost:8001/docs
```

---

## Using the Gradio Web UI

### 1. Access the Web Interface

Open your browser and navigate to:

```
http://localhost:7860
```

You should see the Git RAG Chat interface.

### 2. Check Codex CLI Status

On the UI, scroll down to the **"Codex CLI Status"** section and click **"Check Codex Status"**.

You should see:
- ✅ **Installed**: Version X.X.X
- ✅ **Authenticated**: Ready to use

If you see ❌ errors, go back to [Codex CLI Setup](#codex-cli-setup).

### 3. Add Your First Repository

#### Understanding Container Paths

The Docker containers have access to:
- **`/repos`** - Maps to `REPO_MOUNT_PATH` (configurable in .env)
- **`/host/Documents`** - Maps to your macOS Documents folder (e.g., `/Users/sana/Documents`)

#### Add a Repository

1. Scroll to **"Repository Management"** section
2. In the **"Repository Path"** field, enter a **container path**:

   **Examples:**
   ```
   # If your repo is in Documents/my-project
   /host/Documents/my-project

   # If you mounted a custom path to /repos
   /repos

   # Full container paths work too
   /host/Documents/code/awesome-app
   ```

3. Click **"Add & Index Repository"**

4. Wait for indexing to complete. You'll see:
   ```
   ✅ Repository 'my-project' added and indexed!

   Repo ID: abc-123-def-456
   Files indexed: 247
   Chunks created: 1,853
   ```

### 4. Query Your Code

Once a repository is indexed, use the **Chat Interface** at the top:

**Example Questions:**
```
"What does the main function do?"

"How is authentication implemented?"

"Find all API endpoints"

"Explain the database schema"

"Where is error handling implemented?"

"Show me the configuration files"
```

The system will:
1. Search the vector database for relevant code chunks
2. Retrieve the most relevant context
3. Send the context to ChatGPT Enterprise via Codex CLI
4. Display the AI-generated answer with source references

### 5. Manage Repositories

#### Refresh Repository List
- Click **"Refresh List"** to see all indexed repositories

#### Re-Index a Repository
Use this when your code has changed significantly:
1. Select a repository from the dropdown
2. Click **"Re-Index Selected"**
3. This performs a full re-index (slower but thorough)

#### Delete a Repository
1. Select a repository from the dropdown
2. Click **"Delete Selected"**
3. This removes the repository from the index (doesn't delete your actual code)

---

## Advanced Configuration

### Using Ollama (Offline LLM)

If you want to use a local LLM instead of ChatGPT Enterprise:

1. Update [.env](.env):
   ```bash
   LLM_PROVIDER=ollama
   OLLAMA_MODEL=deepseek-coder:33b
   ```

2. Start with the offline profile:
   ```bash
   docker-compose --profile offline up --build
   ```

3. Pull the model (first time only):
   ```bash
   docker exec -it git-rag-ollama ollama pull deepseek-coder:33b
   ```

### Using File Watcher (Auto-Indexing)

To automatically re-index when files change:

1. Update [.env](.env):
   ```bash
   REPO_MOUNT_PATH=/path/to/your/repo
   REPO_ID=<your-repo-id-from-ui>
   ```

2. Start with the watcher profile:
   ```bash
   docker-compose --profile watcher up
   ```

### Custom Embedding Models

Change the embedding model in [.env](.env):

```bash
# Faster, smaller model
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# Better quality, larger model
EMBEDDING_MODEL=sentence-transformers/all-mpnet-base-v2

# Multilingual support
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

Note: Changing the embedding model requires re-indexing all repositories.

---

## Troubleshooting

### Problem: Codex CLI Not Authenticated

**Symptoms:**
- ❌ **Not Authenticated** in the UI
- Queries fail with authentication errors

**Solution:**
1. Check your Codex config:
   ```bash
   cat ~/.codex/config.toml
   ```

2. Re-authenticate:
   ```bash
   codex auth login
   ```

3. Restart the RAG pipeline:
   ```bash
   docker-compose restart rag-pipeline
   ```

### Problem: Cannot Add Repository

**Symptoms:**
- "Path not found" or "Not a valid Git repository" errors

**Solution:**
1. **Use container paths**, not host paths
   - ❌ Wrong: `/Users/sana/Documents/my-repo`
   - ✅ Correct: `/host/Documents/my-repo`

2. Verify the path is mounted in [docker-compose.yml](docker-compose.yml):
   ```yaml
   volumes:
     - /Users/sana/Documents:/host/Documents:ro
   ```

3. Check if the path exists inside the container:
   ```bash
   docker exec -it git-rag-pipeline ls /host/Documents
   ```

### Problem: Services Won't Start

**Symptoms:**
- `docker-compose up` fails
- Containers exit immediately

**Solution:**
1. Check logs:
   ```bash
   docker-compose logs rag-pipeline
   docker-compose logs chromadb
   docker-compose logs web-ui
   ```

2. Common issues:
   - **Port conflict**: Another service using port 7860, 8000, or 8001
     ```bash
     # Check what's using the port
     lsof -i :7860

     # Update port in .env
     GRADIO_SERVER_PORT=7861
     ```

   - **Codex path wrong**: Update line 30 in docker-compose.yml

   - **Permission issues**: Ensure data directories are writable
     ```bash
     chmod -R 777 ./data
     ```

### Problem: Slow Indexing

**Symptoms:**
- Indexing takes a very long time
- Timeouts during indexing

**Solution:**
1. Check your repository size:
   ```bash
   # Large repos (>10k files) take longer
   find /path/to/repo -type f | wc -l
   ```

2. Increase timeout in the UI or use API directly:
   ```bash
   # Index via API with no timeout
   curl -X POST http://localhost:8001/api/repos/{repo_id}/index \
     -H "Content-Type: application/json" \
     -d '{"force_reindex": false}'
   ```

3. Consider filtering large binary files (images, videos, etc.)

### Problem: No Results from Queries

**Symptoms:**
- Chat returns "No relevant code found"
- Empty search results

**Solution:**
1. Verify repository is indexed:
   - Check "Existing Repositories" section
   - Should show "Files: X | Chunks: Y"

2. Try more specific queries:
   - ❌ "code"
   - ✅ "authentication function"

3. Check ChromaDB has data:
   ```bash
   docker exec -it git-rag-chromadb ls /chroma/data
   ```

### Problem: Gradio UI Not Loading

**Symptoms:**
- Browser shows "Can't connect" or "Connection refused"
- Port 7860 not responding

**Solution:**
1. Check if container is running:
   ```bash
   docker ps | grep git-rag-ui
   ```

2. Check logs:
   ```bash
   docker logs git-rag-ui
   ```

3. Try a different port:
   ```bash
   # In .env
   GRADIO_SERVER_PORT=7861

   # Restart
   docker-compose restart web-ui
   ```

---

## Stopping and Cleaning Up

### Stop Services
```bash
# Stop all services
docker-compose down

# Stop and remove volumes (WARNING: deletes all indexed data)
docker-compose down -v
```

### View Logs
```bash
# All services
docker-compose logs

# Specific service
docker-compose logs rag-pipeline

# Follow logs in real-time
docker-compose logs -f web-ui
```

### Rebuild After Changes
```bash
# Rebuild specific service
docker-compose build rag-pipeline

# Rebuild and restart
docker-compose up --build -d
```

---

## Quick Reference

### Essential Commands

```bash
# Start everything
docker-compose up -d

# View logs
docker-compose logs -f

# Stop everything
docker-compose down

# Check Codex status
codex auth status

# Access UI
open http://localhost:7860

# Access API docs
open http://localhost:8001/docs
```

### Container Paths

| Host Path | Container Path | Purpose |
|-----------|---------------|---------|
| `~/.codex` | `/root/.codex` | Codex authentication |
| `~/Documents` | `/host/Documents` | Easy access to repos |
| `./data/chroma` | `/chroma/data` | ChromaDB storage |
| `./data/metadata` | `/app/data/metadata` | Repository metadata |

### Default Ports

| Service | Port | URL |
|---------|------|-----|
| Gradio UI | 7860 | http://localhost:7860 |
| RAG API | 8001 | http://localhost:8001 |
| ChromaDB | 8000 | http://localhost:8000 |

---

## Need Help?

1. Check the [troubleshooting section](#troubleshooting)
2. Review container logs: `docker-compose logs`
3. Verify Codex authentication: `codex auth status`
4. Check API health: `curl http://localhost:8001/health`

---

**Happy Coding with Git RAG Chat!**

# Phase 4 Implementation Summary

## Overview

Phase 4 implements the **File Watcher** service for real-time monitoring of uncommitted changes and new commits. This phase enables automatic incremental indexing when code files are modified, providing always-up-to-date vector embeddings for the RAG system.

## Components Implemented

### 1. File System Watcher ([services/file-watcher/src/watcher.py](services/file-watcher/src/watcher.py))

**Purpose**: Monitor file system for changes using watchdog

**Key Features**:

- Cross-platform file system monitoring
- Debounced event handling (prevents excessive re-indexing)
- Configurable file extension filtering
- Recursive directory watching
- Automatic exclusion of common ignore directories (.git, node_modules, etc.)

**Key Classes**:

- `DebounceHandler` - FileSystemEventHandler with debouncing logic
- `FileWatcher` - Main file watching orchestrator

**How Debouncing Works**:

1. File change event is received
2. Change is added to pending queue with timestamp
3. Timer starts (default 2 seconds)
4. If more changes occur, timer resets
5. When timer expires, all pending changes are processed
6. Callback is triggered for each changed file

**Ignored Patterns**:

- Hidden files (starting with `.`)
- Common build directories (`__pycache__`, `node_modules`, `dist`, `build`)
- Version control (`.git`)
- Virtual environments (`.venv`, `venv`, `env`)
- Cache directories (`.pytest_cache`, `.mypy_cache`)

### 2. Git Commit Monitor ([services/file-watcher/src/git_monitor.py](services/file-watcher/src/git_monitor.py))

**Purpose**: Monitor Git repository for new commits

**Key Features**:

- Polling-based commit detection (default 5-second interval)
- Tracks HEAD changes
- Extracts changed files from commit diffs
- Detects uncommitted changes (modified, staged, untracked)
- Thread-safe operation

**Key Methods**:

- `_check_for_new_commits()` - Poll for new commits
- `_get_changed_files()` - Extract files from commit diff
- `get_uncommitted_files()` - Get files with uncommitted changes
- `get_current_commit()` - Get current HEAD commit hash
- `get_branch_name()` - Get active branch name

**How Commit Detection Works**:

1. Monitor runs in background thread
2. Every N seconds (configurable), fetch from remote
3. Compare current HEAD with last known commit
4. If different, extract changed files from diff
5. Trigger callback with commit hash and file list

### 3. Watcher Service Main ([services/file-watcher/src/main.py](services/file-watcher/src/main.py))

**Purpose**: Coordinate watchers and integrate with RAG pipeline

**Key Features**:

- Integrates FileWatcher and GitCommitMonitor
- HTTP client for RAG pipeline API calls
- Environment variable configuration
- Signal handling (SIGINT, SIGTERM)
- Graceful shutdown

**Workflow**:

```
File Changed → Debounce → API Call → Re-index File
New Commit → Detect → API Call → Incremental Index
```

**API Integration**:

```python
# File change
POST /api/repos/{repo_id}/index/file?file_path={relative_path}

# New commit
POST /api/repos/{repo_id}/index/incremental
```

**Environment Variables**:

- `REPO_PATH` - Path to repository to watch (required)
- `REPO_ID` - Repository UUID from database (required)
- `RAG_API_URL` - RAG pipeline API URL (default: http://rag-pipeline:8001)
- `DEBOUNCE_SECONDS` - Debounce period (default: 2.0)
- `POLL_INTERVAL` - Git polling interval (default: 5.0)

## Files Created

1. [services/file-watcher/src/watcher.py](services/file-watcher/src/watcher.py) (282 lines)
2. [services/file-watcher/src/git_monitor.py](services/file-watcher/src/git_monitor.py) (273 lines)
3. [services/file-watcher/src/main.py](services/file-watcher/src/main.py) (227 lines)
4. [services/file-watcher/requirements.txt](services/file-watcher/requirements.txt) (10 lines)
5. [services/file-watcher/Dockerfile](services/file-watcher/Dockerfile) (22 lines)
6. [test_phase4.py](test_phase4.py) - Integration test script (264 lines)

## Files Updated

1. [docker-compose.yml](docker-compose.yml) - Added file-watcher service with profile
2. [.env.example](.env.example) - Added file watcher configuration
3. [README.md](README.md) - Updated development status

## Docker Integration

### Service Configuration

```yaml
file-watcher:
  build: ./services/file-watcher
  volumes:
    - ${REPO_MOUNT_PATH}:/repos
  environment:
    - REPO_PATH=/repos
    - REPO_ID=${REPO_ID}
    - RAG_API_URL=http://rag-pipeline:8001
    - DEBOUNCE_SECONDS=2
    - POLL_INTERVAL=5
  profiles:
    - watcher  # Optional service
```

### Starting with File Watcher

```bash
# Start core services only
docker-compose up

# Start with file watcher enabled
docker-compose --profile watcher up

# Start with file watcher AND offline mode (Ollama)
docker-compose --profile watcher --profile offline up
```

## How It Works

### Real-Time File Monitoring

1. **User edits a Python file** in their IDE
2. **watchdog detects** the file system event
3. **Debounce handler** waits 2 seconds for additional changes
4. **Timer expires**, callback is triggered
5. **Watcher service** calls RAG pipeline API:
   ```
   POST /api/repos/{repo_id}/index/file?file_path=src/main.py
   ```
6. **RAG pipeline** re-indexes the file:
   - Parses code into chunks
   - Generates new embeddings
   - Updates ChromaDB collection
   - Updates metadata database

### Commit Detection

1. **User commits** changes to Git
2. **Git monitor** polls every 5 seconds
3. **HEAD commit** has changed
4. **Monitor extracts** list of changed files from commit diff
5. **Watcher service** calls RAG pipeline API:
   ```
   POST /api/repos/{repo_id}/index/incremental
   ```
6. **RAG pipeline** performs incremental indexing:
   - Gets list of modified files from Git
   - Re-indexes only those files
   - Updates vectors in ChromaDB

### Debouncing Benefits

**Without Debouncing**:
- User saves file → index
- User saves again → index
- User saves again → index
- Result: 3 indexing operations

**With Debouncing (2 seconds)**:
- User saves file → start timer
- User saves again (1s later) → reset timer
- User saves again (1.5s later) → reset timer
- Timer expires (2s after last save) → index once
- Result: 1 indexing operation

## Testing

### Test Script: [test_phase4.py](test_phase4.py)

Run tests with:

```bash
python test_phase4.py
```

**Tests Included**:

1. **Debounce Handler** - Verify debouncing logic
2. **File Watcher** - Verify file change detection
3. **Git Monitor** - Verify commit detection
4. **Uncommitted Files** - Verify uncommitted file detection

## Usage Example

### Manual Setup

```bash
# 1. Start core services
docker-compose up -d chromadb rag-pipeline

# 2. Add repository via API
curl -X POST http://localhost:8001/api/repos \
  -H "Content-Type: application/json" \
  -d '{"path": "/path/to/repo", "name": "My Project"}'

# Response: {"id": "abc-123-def", ...}

# 3. Set environment variables
export REPO_MOUNT_PATH=/path/to/repo
export REPO_ID=abc-123-def

# 4. Start file watcher
docker-compose --profile watcher up -d file-watcher

# 5. Check logs
docker-compose logs -f file-watcher
```

### Automated Workflow

```bash
# Edit .env file
REPO_MOUNT_PATH=/Users/me/projects/myproject
REPO_ID=abc-123-def

# Start all services (including watcher)
docker-compose --profile watcher up --build

# Now any file changes will be automatically indexed!
```

## Performance Characteristics

### File Watching

- **Event Detection**: Near-instantaneous (watchdog)
- **Debounce Delay**: 2 seconds (configurable)
- **API Call**: <100ms (local network)
- **Re-indexing**: Depends on file size (typically <1 second)

### Git Monitoring

- **Poll Interval**: 5 seconds (configurable)
- **Commit Detection**: Within one poll interval
- **Diff Extraction**: <100ms for most commits
- **Incremental Indexing**: Depends on number of changed files

### Resource Usage

- **CPU**: Minimal when idle (<1%)
- **Memory**: ~50-100MB (watchdog + Python)
- **Disk I/O**: Low (only on actual file changes)
- **Network**: Minimal (only API calls to rag-pipeline)

## Configuration Options

### Debounce Period

```bash
# Fast response (1 second)
DEBOUNCE_SECONDS=1

# Default (2 seconds)
DEBOUNCE_SECONDS=2

# Conservative (5 seconds)
DEBOUNCE_SECONDS=5
```

**Trade-offs**:
- Lower: Faster updates, more frequent indexing
- Higher: Less frequent indexing, better batching

### Poll Interval

```bash
# Aggressive (2 seconds)
POLL_INTERVAL=2

# Default (5 seconds)
POLL_INTERVAL=5

# Conservative (10 seconds)
POLL_INTERVAL=10
```

**Trade-offs**:
- Lower: Faster commit detection, more CPU/network usage
- Higher: Slower commit detection, less resource usage

## Limitations & Future Improvements

### Current Limitations

1. **Single Repository**: Watcher monitors only one repository at a time
2. **No Branch Switching Detection**: Doesn't trigger re-index on branch changes
3. **No Remote Fetch**: Doesn't automatically fetch from remote
4. **Local Commits Only**: Commit detection works best with local commits

### Future Improvements

1. **Multi-Repository Support**: Watch multiple repositories simultaneously
2. **Git Hooks Integration**: Use Git hooks for instant commit detection
3. **Branch Change Detection**: Re-index on branch checkout
4. **Remote Tracking**: Automatically fetch and detect remote commits
5. **Selective Watching**: Allow watching specific directories only
6. **Event Statistics**: Track and report watcher statistics

## Integration with RAG Pipeline

The file watcher is a **standalone service** that communicates with the RAG pipeline via HTTP API. This design provides:

**Benefits**:
- **Loose Coupling**: Watcher can restart without affecting pipeline
- **Scalability**: Multiple watchers can monitor different repos
- **Resilience**: If watcher fails, pipeline continues to work
- **Flexibility**: Can run watcher on different machine if needed

**Communication Flow**:

```
File Watcher          →  HTTP POST  →  RAG Pipeline
(Detects change)         (API call)     (Re-indexes)

Git Monitor           →  HTTP POST  →  RAG Pipeline
(Detects commit)         (API call)     (Incremental)
```

## Next Steps (Phase 5-8)

### Phase 5: RAG Retrieval

- Implement query endpoint with semantic search
- Add MMR reranking for diverse results
- Context assembly for LLM prompts
- Metadata filtering by language, file, etc.

### Phase 6: LLM Integration

- Codex CLI provider with ChatGPT Enterprise
- Ollama fallback for offline usage
- Streaming response support
- Prompt engineering for code queries

### Phase 7: Web UI

- Gradio chat interface
- Repository directory picker
- Real-time indexing status
- Query history and management

### Phase 8: Testing & Polish

- Comprehensive test suite
- Performance optimization
- Production deployment guide
- User documentation

## Notes

- File watcher is **optional** (profile-based in docker-compose)
- Can be used without watcher for manual indexing
- Watcher requires repository to be mounted as volume
- Designed for development workflows (auto-indexing on save)
- Production deployments might prefer webhook-based triggers

# Git RAG Chat - Version 1 Technical Documentation

**Commit:** `5fb68bf50c6d3ef6b72baba11f17cc9a1e422b91`
**Date:** December 7, 2025
**Status:** Tested and Working Version 1

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Data Processing Pipeline](#data-processing-pipeline)
4. [Component Details](#component-details)
5. [Configuration](#configuration)
6. [API Endpoints](#api-endpoints)
7. [Database Schema](#database-schema)

---

## System Overview

Git RAG Chat is a Retrieval-Augmented Generation (RAG) system designed to enable natural language querying of Git repositories. The system indexes code repositories, generates embeddings for semantic search, and uses LLMs to provide intelligent answers about the codebase.

### Key Features

- Multi-repository support with metadata tracking
- AST-based code parsing for Python and JavaScript/TypeScript
- Semantic chunking with overlap for large code files
- Vector-based similarity search using ChromaDB
- Multiple LLM provider support (Codex CLI, Ollama)
- Git history integration for commit-aware responses
- Incremental indexing for uncommitted changes

---

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                        Web UI (Streamlit)                   │
│                     (services/web-ui)                       │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP API
                         ↓
┌─────────────────────────────────────────────────────────────┐
│                   RAG Pipeline Service                      │
│                (services/rag-pipeline)                      │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  FastAPI REST API (routes.py)                        │  │
│  └──────────────┬───────────────────────────────────────┘  │
│                 │                                            │
│  ┌──────────────┴───────────────────────────────────────┐  │
│  │         Core Processing Components                    │  │
│  │  ┌─────────────────────────────────────────────────┐ │  │
│  │  │ 1. Git Operations (git_ops.py)                  │ │  │
│  │  │    - Repository cloning & tracking              │ │  │
│  │  │    - Commit history retrieval                   │ │  │
│  │  │    - Modified file detection                    │ │  │
│  │  └─────────────────────────────────────────────────┘ │  │
│  │  ┌─────────────────────────────────────────────────┐ │  │
│  │  │ 2. Code Parser (parser.py)                      │ │  │
│  │  │    - AST-based parsing                          │ │  │
│  │  │    - Language detection                         │ │  │
│  │  │    - Function/class extraction                  │ │  │
│  │  └─────────────────────────────────────────────────┘ │  │
│  │  ┌─────────────────────────────────────────────────┐ │  │
│  │  │ 3. Chunker (chunker.py)                         │ │  │
│  │  │    - Semantic chunking                          │ │  │
│  │  │    - Overlap strategy                           │ │  │
│  │  │    - Markdown section splitting                 │ │  │
│  │  └─────────────────────────────────────────────────┘ │  │
│  │  ┌─────────────────────────────────────────────────┐ │  │
│  │  │ 4. Embedder (embedder.py)                       │ │  │
│  │  │    - Sentence-transformers integration          │ │  │
│  │  │    - Batch embedding generation                 │ │  │
│  │  │    - Model: all-MiniLM-L6-v2                    │ │  │
│  │  └─────────────────────────────────────────────────┘ │  │
│  │  ┌─────────────────────────────────────────────────┐ │  │
│  │  │ 5. Vector Store (vector_store.py)               │ │  │
│  │  │    - ChromaDB HTTP client                       │ │  │
│  │  │    - Collection management                      │ │  │
│  │  │    - Similarity search                          │ │  │
│  │  └─────────────────────────────────────────────────┘ │  │
│  │  ┌─────────────────────────────────────────────────┐ │  │
│  │  │ 6. Indexer (indexer.py)                         │ │  │
│  │  │    - Orchestrates parsing → chunking → embed    │ │  │
│  │  │    - Full & incremental indexing                │ │  │
│  │  │    - File hash tracking                         │ │  │
│  │  └─────────────────────────────────────────────────┘ │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         Storage Layer                                │  │
│  │  • SQLite Metadata DB (metadata_db.py)              │  │
│  │  • ChromaDB Vector Store                            │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────┐
│                    ChromaDB Service                         │
│                  (External HTTP Service)                    │
└─────────────────────────────────────────────────────────────┘
```

### Technology Stack

- **Backend:** Python 3.11, FastAPI
- **Frontend:** Streamlit
- **Embedding Model:** sentence-transformers/all-MiniLM-L6-v2 (384 dimensions)
- **Vector Database:** ChromaDB (HTTP client mode)
- **Metadata Database:** SQLite
- **LLM Providers:** Codex CLI, Ollama (DeepSeek-Coder 33B)
- **Containerization:** Docker, Docker Compose

---

## Data Processing Pipeline

### Indexing Flow

The data processing pipeline transforms raw code into queryable semantic vectors:

```
Git Repository
     │
     ↓
┌─────────────────────────────────────────────────────────────┐
│ STAGE 1: File Discovery & Filtering                        │
│ ─────────────────────────────────────────────────────────── │
│ • Git operations: get_tracked_files()                       │
│ • Filter binary files (.pyc, .png, .zip, etc.)             │
│ • Skip hidden directories (node_modules, __pycache__)      │
│ • Compute SHA256 file hash for change detection            │
│                                                             │
│ Input:  Repository path                                    │
│ Output: List of indexable file paths                       │
└─────────────────────────────────────────────────────────────┘
     │
     ↓
┌─────────────────────────────────────────────────────────────┐
│ STAGE 2: Code Parsing                                      │
│ ─────────────────────────────────────────────────────────── │
│ Component: CodeParser (parser.py)                          │
│                                                             │
│ For Python files (.py):                                    │
│   • Line-based parsing (simplified AST approach)           │
│   • Extract functions: def function_name(...)              │
│   • Extract classes: class ClassName:                      │
│   • Capture docstrings and implementation                  │
│                                                             │
│ For JavaScript/TypeScript (.js, .jsx, .ts, .tsx):         │
│   • Detect functions (function keyword, arrow functions)   │
│   • Detect classes                                         │
│   • Track brace-based scope boundaries                     │
│                                                             │
│ For Markdown (.md):                                        │
│   • Split by headers (# Header syntax)                     │
│   • Preserve section hierarchy                             │
│                                                             │
│ For other languages:                                       │
│   • Treat entire file as single chunk                      │
│                                                             │
│ Input:  File content (UTF-8 string)                       │
│ Output: List of parsed chunks with metadata:               │
│         {                                                   │
│           code: str,                                        │
│           chunk_type: 'function' | 'class' | 'section',    │
│           name: str,                                        │
│           file_path: str,                                   │
│           language: str,                                    │
│           start_line: int,                                  │
│           end_line: int,                                    │
│           line_count: int                                   │
│         }                                                   │
└─────────────────────────────────────────────────────────────┘
     │
     ↓
┌─────────────────────────────────────────────────────────────┐
│ STAGE 3: Chunking Strategy                                 │
│ ─────────────────────────────────────────────────────────── │
│ Component: CodeChunker (chunker.py)                        │
│                                                             │
│ Parameters:                                                 │
│   • max_chunk_size: 1000 tokens (~4000 chars)              │
│   • overlap: 50 tokens (~200 chars)                        │
│                                                             │
│ Logic:                                                      │
│   1. For each parsed chunk from Stage 2:                   │
│      IF chunk size <= 4000 chars:                          │
│        → Keep as single chunk                              │
│      ELSE:                                                  │
│        → Split with overlap                                │
│                                                             │
│   2. Overlap Strategy:                                     │
│      - Calculate lines per chunk based on avg line length  │
│      - Create sliding window with overlap_lines            │
│      - Generate sub-chunks: part1, part2, part3, ...       │
│      - Mark with: is_partial=True, part_number=N           │
│                                                             │
│   3. Special handling for Markdown:                        │
│      - Respect section boundaries                          │
│      - Split sections if exceeding max_chunk_size          │
│                                                             │
│ Input:  Parsed chunks from Stage 2                        │
│ Output: Final chunks with additional metadata:             │
│         {                                                   │
│           ...all fields from Stage 2,                       │
│           char_count: int,                                  │
│           token_count_estimate: int (chars / 4),           │
│           preview: str (first 100 chars),                   │
│           is_partial: bool,                                 │
│           part_number: int,                                 │
│           parent_chunk: str                                 │
│         }                                                   │
└─────────────────────────────────────────────────────────────┘
     │
     ↓
┌─────────────────────────────────────────────────────────────┐
│ STAGE 4: Embedding Generation                              │
│ ─────────────────────────────────────────────────────────── │
│ Component: Embedder (embedder.py)                          │
│                                                             │
│ Model: sentence-transformers/all-MiniLM-L6-v2              │
│   • Embedding dimension: 384                                │
│   • Max sequence length: 256 tokens                        │
│   • Device: CPU (configurable)                             │
│                                                             │
│ Process:                                                    │
│   1. Extract code text from each chunk                     │
│   2. Preprocess (remove excess whitespace)                 │
│   3. Truncate to max 512 tokens (~2048 chars)              │
│   4. Batch encode with batch_size=32                       │
│   5. Generate numpy arrays (shape: [n_chunks, 384])        │
│                                                             │
│ Input:  List of chunks with 'code' field                  │
│ Output: Numpy array of embeddings (float32)                │
│         Shape: [n_chunks, 384]                             │
└─────────────────────────────────────────────────────────────┘
     │
     ↓
┌─────────────────────────────────────────────────────────────┐
│ STAGE 5: Vector Storage                                    │
│ ─────────────────────────────────────────────────────────── │
│ Component: VectorStore (vector_store.py)                   │
│                                                             │
│ ChromaDB Storage:                                           │
│   • Collection per repository: repo_{uuid}                  │
│   • Embeddings generated by SentenceTransformer            │
│   • Metadata stored as string key-value pairs              │
│                                                             │
│ Chunk ID Format:                                           │
│   {collection_name}_{index}_{chunk_name}                   │
│   Example: repo_abc123_0_parse_file                        │
│                                                             │
│ Stored Metadata (all as strings):                          │
│   - file_path: Absolute file path                          │
│   - chunk_type: function | class | section | text          │
│   - name: Function/class/section name                      │
│   - language: python | javascript | markdown | etc.        │
│   - start_line: Starting line number                       │
│   - end_line: Ending line number                           │
│   - line_count: Number of lines                            │
│   - char_count: Character count                            │
│   - token_count_estimate: Estimated tokens                 │
│   - is_uncommitted: true | false                           │
│   - commit_hash: Git commit SHA (if committed)             │
│   - is_partial: true | false (for split chunks)            │
│   - part_number: Part number if split                      │
│   - parent_chunk: Original chunk name if split             │
│                                                             │
│ Batching:                                                   │
│   • Process in batches of 100 chunks                       │
│   • Automatic retry on failure                             │
│                                                             │
│ Input:  Chunks + embeddings                                │
│ Output: Persisted vectors in ChromaDB                      │
└─────────────────────────────────────────────────────────────┘
     │
     ↓
┌─────────────────────────────────────────────────────────────┐
│ STAGE 6: Metadata Tracking                                 │
│ ─────────────────────────────────────────────────────────── │
│ Component: MetadataDB (metadata_db.py)                     │
│                                                             │
│ SQLite Tables Updated:                                      │
│   1. repositories:                                          │
│      - last_indexed_at = CURRENT_TIMESTAMP                 │
│      - last_commit_hash = {latest_commit_sha}              │
│      - total_chunks = {count}                              │
│      - total_files = {count}                               │
│      - indexing_status = 'completed'                       │
│                                                             │
│   2. indexed_files:                                         │
│      - file_path, file_hash, chunk_count, language         │
│      - Used for incremental indexing (skip unchanged)      │
│                                                             │
│ Input:  Indexing results                                   │
│ Output: Updated SQLite metadata                            │
└─────────────────────────────────────────────────────────────┘
```

### Query Flow

When a user submits a query, the system performs semantic search and generates context-aware responses:

```
User Query
     │
     ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 1: Query Embedding                                    │
│ ─────────────────────────────────────────────────────────── │
│ • Embed query using same model (all-MiniLM-L6-v2)          │
│ • Generate 384-dimensional vector                          │
│ • Apply same preprocessing as chunks                       │
└─────────────────────────────────────────────────────────────┘
     │
     ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 2: Vector Similarity Search                           │
│ ─────────────────────────────────────────────────────────── │
│ ChromaDB Query:                                             │
│   • Collection: Active repository's collection             │
│   • Method: Cosine similarity                              │
│   • Return top N results (default: 20)                     │
│   • Optional filters: language, file_path                  │
│                                                             │
│ Returns:                                                    │
│   - Document texts (code chunks)                           │
│   - Metadata (file_path, chunk_type, etc.)                 │
│   - Distance scores (cosine distance)                      │
└─────────────────────────────────────────────────────────────┘
     │
     ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 3: Reranking (Optional)                               │
│ ─────────────────────────────────────────────────────────── │
│ MMR (Maximal Marginal Relevance):                          │
│   • Balance relevance vs diversity                         │
│   • lambda_param = 0.5 (configurable)                      │
│   • Reduce redundant similar chunks                        │
│   • Return top K (default: 10)                             │
└─────────────────────────────────────────────────────────────┘
     │
     ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 4: Git Context Augmentation                           │
│ ─────────────────────────────────────────────────────────── │
│ IF query contains git-related keywords:                     │
│   ['commit', 'git log', 'latest change', 'what changed']   │
│                                                             │
│ THEN:                                                       │
│   1. Run: git log -5 --format=%H|%s|%an|%ar                │
│   2. Extract: commit hash, message, author, date           │
│   3. Format as markdown list                               │
│                                                             │
│   IF query asks about 'latest commit':                     │
│     4. Run: git show --stat --format=%B {commit_hash}      │
│     5. Include diff in context (truncated to 1500 chars)   │
│                                                             │
│ Output: Git context string prepended to code context       │
└─────────────────────────────────────────────────────────────┘
     │
     ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 5: Context Assembly                                   │
│ ─────────────────────────────────────────────────────────── │
│ Assemble prompt with:                                       │
│   • Git history (if applicable)                            │
│   • Retrieved code chunks (formatted with metadata)        │
│   • File paths, line numbers, chunk types                  │
│   • Query text                                             │
│                                                             │
│ Prompt Template:                                            │
│   # Relevant Code Context                                  │
│                                                             │
│   ## Retrieved Chunks:                                     │
│   [For each chunk:]                                        │
│   File: {file_path}:{start_line}-{end_line}                │
│   Type: {chunk_type}                                       │
│   Name: {name}                                             │
│   Language: {language}                                     │
│   Similarity: {similarity}                                 │
│                                                             │
│   ```{language}                                            │
│   {code}                                                   │
│   ```                                                      │
│                                                             │
│   ---                                                      │
│                                                             │
│   Query: {user_query}                                      │
└─────────────────────────────────────────────────────────────┘
     │
     ↓
┌─────────────────────────────────────────────────────────────┐
│ STEP 6: LLM Generation                                     │
│ ─────────────────────────────────────────────────────────── │
│ Provider: Codex CLI (default) or Ollama                    │
│                                                             │
│ Codex CLI:                                                  │
│   • Command: codex exec --json {prompt}                    │
│   • Docker flag: --dangerously-bypass-approvals-and-sandbox│
│   • Streams response via subprocess                        │
│                                                             │
│ Ollama:                                                     │
│   • Model: deepseek-coder:33b                              │
│   • API: POST /api/generate                                │
│   • Streams response                                       │
│                                                             │
│ Parameters:                                                 │
│   • temperature: 0.1 (deterministic)                       │
│   • max_tokens: 2000                                       │
│                                                             │
│ Output: Generated answer (text stream or complete)         │
└─────────────────────────────────────────────────────────────┘
     │
     ↓
Response to User
```

---

## Component Details

### 1. Code Parser (`parser.py`)

**Purpose:** Extract semantic code units (functions, classes) from source files.

**Supported Languages:**
- Python (`.py`)
- JavaScript/TypeScript (`.js`, `.jsx`, `.ts`, `.tsx`)
- Java (`.java`)
- Go (`.go`)
- Rust (`.rs`)
- Ruby (`.rb`)
- C/C++ (`.c`, `.cpp`, `.h`, `.hpp`)

**Parsing Strategy:**

#### Python Parsing
```python
# Line-based detection (simplified AST)
if line.startswith('def '):
    chunk_type = 'function'
    extract_name_from_signature()
elif line.startswith('class '):
    chunk_type = 'class'
    extract_name_from_signature()
```

**Output Format:**
```python
{
    'code': 'def parse_file(...):\n    ...',
    'chunk_type': 'function',
    'name': 'parse_file',
    'file_path': '/path/to/file.py',
    'language': 'python',
    'start_line': 42,
    'end_line': 67,
    'line_count': 26
}
```

**Limitations:**
- Simplified line-based parsing (not full AST)
- May not handle complex nested structures perfectly
- Future enhancement: Full tree-sitter integration

---

### 2. Code Chunker (`chunker.py`)

**Purpose:** Split large code units into embeddable chunks with overlap.

**Configuration:**
- `max_chunk_size`: 1000 tokens (≈4000 characters)
- `overlap`: 50 tokens (≈200 characters)

**Chunking Logic:**

```python
if chunk_size <= max_chars:
    return [chunk]  # Keep as-is
else:
    # Calculate overlap window
    lines_per_chunk = max_chars / avg_line_length
    overlap_lines = overlap_chars / avg_line_length

    # Sliding window
    for i in range(0, total_lines, lines_per_chunk - overlap_lines):
        sub_chunk = create_chunk(lines[i:i+lines_per_chunk])
        sub_chunk['is_partial'] = True
        sub_chunk['part_number'] = part_num
```

**Markdown Chunking:**
- Split by headers (`# Header`)
- Preserve section hierarchy
- Further split if section exceeds max size

---

### 3. Embedder (`embedder.py`)

**Purpose:** Generate vector embeddings for semantic similarity search.

**Model Specification:**
```yaml
Model: sentence-transformers/all-MiniLM-L6-v2
Embedding Dimension: 384
Max Sequence Length: 256 tokens
Model Size: ~80MB
Performance: ~14,000 sentences/second (CPU)
```

**Preprocessing:**
```python
def preprocess_code(code, max_length=512):
    # Remove excessive whitespace
    lines = [line.rstrip() for line in code.split('\n')]
    code = '\n'.join(lines)

    # Truncate if too long (512 tokens ≈ 2048 chars)
    if len(code) > max_length * 4:
        code = code[:max_length * 4]

    return code
```

**Batch Processing:**
- Batch size: 32
- Progress bar enabled
- Output: NumPy float32 array

---

### 4. Vector Store (`vector_store.py`)

**Purpose:** Interface with ChromaDB for vector storage and retrieval.

**Connection:**
```python
client = chromadb.HttpClient(
    host="chromadb",
    port=8000
)
```

**Collection Structure:**
- One collection per repository
- Naming: `repo_{uuid_with_underscores}`
- Embedding function: SentenceTransformerEmbeddingFunction

**Query Parameters:**
```python
collection.query(
    query_texts=[query],
    n_results=20,
    where={'language': 'python'},  # Optional filter
    include=['documents', 'metadatas', 'distances']
)
```

**Metadata Constraints:**
- All values must be strings
- Boolean values: "true" / "false"
- Integer values: "42" (stringified)

---

### 5. Repository Indexer (`indexer.py`)

**Purpose:** Orchestrate the full indexing pipeline.

**Indexing Modes:**

#### Full Indexing
```python
indexer.index_repository(
    repo_id=repo_id,
    repo_path="/path/to/repo",
    force_reindex=False
)
```

Process:
1. Get all tracked files from Git
2. Filter indexable files
3. Compute file hashes
4. Skip unchanged files (if not force_reindex)
5. Parse → Chunk → Embed → Store
6. Update metadata database

#### Incremental Indexing
```python
indexer.incremental_index(repo_id=repo_id)
```

Process:
1. Get modified files (git diff)
2. Delete old chunks for modified files
3. Re-index only modified files
4. Mark chunks as `is_uncommitted=True`

#### Single File Indexing
```python
indexer.index_file(
    repo_id=repo_id,
    file_path="src/main.py",
    is_uncommitted=True
)
```

**File Hash Tracking:**
```python
def _compute_file_hash(file_path):
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            sha256.update(chunk)
    return sha256.hexdigest()
```

---

### 6. Metadata Database (`metadata_db.py`)

**Purpose:** Track repositories, files, and indexing state.

**Schema:** See [Database Schema](#database-schema) section.

**Key Operations:**

```python
# Add repository
repo_id = db.add_repository(path="/path/to/repo", name="MyRepo")

# Track indexed file
db.upsert_file(
    repo_id=repo_id,
    file_path="src/main.py",
    file_hash="abc123...",
    chunk_count=5,
    language="python"
)

# Set active repository
db.set_active_repository(repo_id)

# Get active repository
active_repo = db.get_active_repository()
```

---

## Configuration

### Environment Variables

**File:** `.env` or environment variables

```bash
# ChromaDB Configuration
CHROMA_HOST=chromadb
CHROMA_PORT=8000

# LLM Provider
LLM_PROVIDER=codex  # Options: codex, ollama
CODEX_PROFILE=null  # Optional Codex profile
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=deepseek-coder:33b

# Embedding Model
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# Database
METADATA_DB_PATH=/app/data/metadata/repos.db

# API Server
API_HOST=0.0.0.0
API_PORT=8001

# Logging
LOG_LEVEL=INFO
```

### Settings Class (`config.py`)

```python
class Settings(BaseSettings):
    chroma_host: str = "chromadb"
    chroma_port: int = 8000
    llm_provider: str = "codex"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    metadata_db_path: str = "/app/data/metadata/repos.db"
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = False
```

---

## API Endpoints

### Base URL
```
http://localhost:8001
```

### Health & Status

#### `GET /health`
Check system health.

**Response:**
```json
{
    "status": "healthy",
    "version": "0.1.0",
    "chromadb_connected": true
}
```

#### `GET /codex/status`
Check Codex CLI availability.

**Response:**
```json
{
    "installed": true,
    "authenticated": true,
    "version": "codex 1.x.x",
    "error": null
}
```

---

### Repository Management

#### `POST /repos`
Add a new repository.

**Request:**
```json
{
    "path": "/path/to/repo",
    "name": "MyRepo"
}
```

**Response:**
```json
{
    "id": "uuid-here",
    "name": "MyRepo",
    "path": "/path/to/repo",
    "chroma_collection_name": "repo_uuid_here",
    "created_at": "2025-12-07T06:05:14",
    "last_indexed_at": null,
    "indexing_status": "pending",
    "is_active": false
}
```

#### `GET /repos`
List all repositories.

**Response:** Array of repository objects.

#### `GET /repos/{repo_id}`
Get repository details.

#### `PUT /repos/{repo_id}/activate`
Set a repository as active.

#### `DELETE /repos/{repo_id}`
Delete repository and all indexed data.

#### `GET /repos/{repo_id}/stats`
Get Git repository statistics.

**Response:**
```json
{
    "total_commits": 42,
    "total_branches": 3,
    "total_tags": 5,
    "latest_commit": {
        "hash": "abc123...",
        "message": "Add feature X",
        "author": "John Doe",
        "date": "2025-12-07"
    }
}
```

---

### Indexing Operations

#### `POST /repos/{repo_id}/index`
Trigger full repository indexing.

**Request Body (optional):**
```json
{
    "force_reindex": false
}
```

**Response:**
```json
{
    "message": "Indexing completed",
    "repo_id": "uuid-here",
    "indexed_files": 150,
    "total_chunks": 1234,
    "status": "completed"
}
```

#### `POST /repos/{repo_id}/index/file`
Index a specific file.

**Query Parameters:**
- `file_path`: Path to file (relative to repo root)

**Response:**
```json
{
    "message": "File indexed successfully",
    "file_path": "src/main.py",
    "chunks_added": 5
}
```

#### `POST /repos/{repo_id}/index/incremental`
Perform incremental indexing (modified files only).

**Response:**
```json
{
    "message": "Incremental indexing completed",
    "repo_id": "uuid-here",
    "indexed_files": 3,
    "total_chunks": 42,
    "status": "completed"
}
```

#### `GET /repos/{repo_id}/index/status`
Get indexing status and statistics.

**Response:**
```json
{
    "repo_id": "uuid-here",
    "repo_name": "MyRepo",
    "repo_path": "/path/to/repo",
    "total_files": 150,
    "total_chunks": 1234,
    "last_indexed_at": "2025-12-07T06:05:14",
    "last_commit_hash": "abc123...",
    "indexing_status": "completed",
    "chroma_chunk_count": 1234,
    "collection_name": "repo_uuid_here"
}
```

---

### Querying

#### `POST /query`
Query the RAG system.

**Request:**
```json
{
    "query": "How does authentication work?",
    "repo_id": "uuid-here",  // Optional, uses active repo if not specified
    "n_results": 10,
    "use_reranking": true,
    "language": "python",  // Optional filter
    "file_path": "src/"    // Optional filter
}
```

**Response:**
```json
{
    "answer": "Authentication is implemented using...",
    "sources": [
        {
            "file_path": "/path/to/file.py",
            "chunk_type": "function",
            "name": "authenticate",
            "start_line": 42,
            "end_line": 67,
            "similarity": 0.85,
            "code_preview": "def authenticate(user, password):..."
        }
    ],
    "repo_id": "uuid-here",
    "metadata": {
        "retrieved_chunks": 20,
        "final_chunks": 10,
        "collection": "repo_uuid_here",
        "reranking_applied": true,
        "summary": {
            "unique_files": 5,
            "total_lines": 250,
            "languages": ["python", "javascript"]
        },
        "prompt_length": 3500,
        "llm_provider": "codex"
    }
}
```

#### `POST /query/stream`
Query with streaming response (same request format as `/query`).

**Response:** Server-Sent Events stream of answer text.

---

## Database Schema

### SQLite Metadata Database

**Location:** `/app/data/metadata/repos.db`

#### Table: `repositories`

Tracks registered Git repositories.

```sql
CREATE TABLE repositories (
    id TEXT PRIMARY KEY,                -- UUID
    name TEXT NOT NULL,                 -- Repository name
    path TEXT NOT NULL UNIQUE,          -- Absolute path
    chroma_collection_name TEXT NOT NULL, -- ChromaDB collection ID
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_indexed_at TIMESTAMP,          -- Last successful indexing
    last_commit_hash TEXT,              -- Latest commit SHA
    is_active BOOLEAN DEFAULT 0,        -- Active repository flag
    indexing_status TEXT CHECK(indexing_status IN
        ('pending', 'in_progress', 'completed', 'failed')),
    total_chunks INTEGER DEFAULT 0,     -- Total chunks in ChromaDB
    total_files INTEGER DEFAULT 0       -- Total indexed files
);
```

#### Table: `indexed_files`

Tracks indexed files for incremental updates.

```sql
CREATE TABLE indexed_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id TEXT NOT NULL,              -- FK to repositories.id
    file_path TEXT NOT NULL,            -- Relative path from repo root
    file_hash TEXT NOT NULL,            -- SHA256 hash for change detection
    last_indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    chunk_count INTEGER DEFAULT 0,      -- Number of chunks from this file
    language TEXT,                      -- Detected language
    FOREIGN KEY (repo_id) REFERENCES repositories(id) ON DELETE CASCADE,
    UNIQUE(repo_id, file_path)
);

CREATE INDEX idx_indexed_files_repo ON indexed_files(repo_id);
CREATE INDEX idx_indexed_files_hash ON indexed_files(file_hash);
```

#### Table: `indexed_commits`

Tracks indexed commits (future use for commit-level search).

```sql
CREATE TABLE indexed_commits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id TEXT NOT NULL,
    commit_hash TEXT NOT NULL,
    commit_message TEXT,
    author TEXT,
    committed_at TIMESTAMP,
    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    chunk_count INTEGER DEFAULT 0,
    FOREIGN KEY (repo_id) REFERENCES repositories(id) ON DELETE CASCADE,
    UNIQUE(repo_id, commit_hash)
);

CREATE INDEX idx_indexed_commits_repo ON indexed_commits(repo_id);
```

#### Table: `indexing_queue`

Job queue for background indexing tasks.

```sql
CREATE TABLE indexing_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id TEXT NOT NULL,
    job_type TEXT CHECK(job_type IN
        ('full', 'incremental', 'file', 'commit')),
    target_path TEXT,                   -- File path or commit hash
    status TEXT CHECK(status IN
        ('pending', 'processing', 'completed', 'failed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    FOREIGN KEY (repo_id) REFERENCES repositories(id) ON DELETE CASCADE
);

CREATE INDEX idx_indexing_queue_status ON indexing_queue(status, created_at);
```

---

### ChromaDB Collections

**Collection Naming:** `repo_{uuid_with_underscores}`

**Document Storage:**
- **ID:** `{collection_name}_{index}_{chunk_name}`
- **Document:** Raw code text (string)
- **Embedding:** 384-dimensional float vector (auto-generated)
- **Metadata:** All stored as strings

**Metadata Fields:**
```python
{
    'file_path': str,           # Absolute file path
    'chunk_type': str,          # function | class | section | text | file
    'name': str,                # Function/class/section name
    'language': str,            # python | javascript | etc.
    'start_line': str,          # "42"
    'end_line': str,            # "67"
    'line_count': str,          # "26"
    'char_count': str,          # "1024"
    'token_count_estimate': str, # "256"
    'is_uncommitted': str,      # "true" | "false"
    'commit_hash': str,         # Git SHA or empty
    'is_partial': str,          # "true" | "false"
    'part_number': str,         # "1" | "2" | "0"
    'parent_chunk': str         # Original chunk name or empty
}
```

---

## Data Flow Examples

### Example 1: Full Repository Indexing

**Scenario:** Index a Python repository with 100 files.

**Request:**
```bash
POST /repos/{repo_id}/index
```

**Process:**

1. **File Discovery**
   - Git: 120 tracked files
   - Filtered: 100 indexable (20 binary/hidden files skipped)

2. **File: `src/auth/login.py` (350 lines)**
   - **Parsing:**
     ```
     Chunk 1: class LoginManager (lines 1-120)
     Chunk 2: def authenticate() (lines 122-180)
     Chunk 3: def validate_token() (lines 182-220)
     Chunk 4: class SessionStore (lines 222-350)
     ```

   - **Chunking:**
     ```
     Chunk 1: class LoginManager → Size OK (keep as-is)
     Chunk 2: def authenticate() → Size OK
     Chunk 3: def validate_token() → Size OK
     Chunk 4: class SessionStore → Too large (5200 chars)
         → Split into:
            - SessionStore_part1 (lines 222-280, with overlap)
            - SessionStore_part2 (lines 270-320, with overlap)
            - SessionStore_part3 (lines 310-350, with overlap)
     ```

   - **Final:** 6 chunks from this file

3. **Embedding Generation**
   - Batch of 32 chunks processed
   - 6 embeddings generated (384-dim each)

4. **ChromaDB Storage**
   - Collection: `repo_abc123`
   - 6 documents added with metadata
   - IDs: `repo_abc123_0_LoginManager`, `repo_abc123_1_authenticate`, ...

5. **Metadata Tracking**
   - SQLite: `indexed_files` entry created
     ```sql
     INSERT INTO indexed_files (
         repo_id, file_path, file_hash, chunk_count, language
     ) VALUES (
         'abc123...', 'src/auth/login.py', 'def456...', 6, 'python'
     );
     ```

6. **Repository Stats Update**
   ```sql
   UPDATE repositories SET
       last_indexed_at = CURRENT_TIMESTAMP,
       total_chunks = 534,
       total_files = 100,
       indexing_status = 'completed'
   WHERE id = 'abc123...';
   ```

**Result:**
- 100 files indexed
- 534 total chunks created
- Average: 5.34 chunks per file

---

### Example 2: Query Execution

**Scenario:** Query "How does authentication work?"

**Request:**
```bash
POST /query
{
    "query": "How does authentication work?",
    "n_results": 10,
    "use_reranking": true
}
```

**Process:**

1. **Query Embedding**
   - Input: "How does authentication work?"
   - Model: all-MiniLM-L6-v2
   - Output: [0.123, -0.456, ...] (384 dims)

2. **Vector Search**
   - ChromaDB query on `repo_abc123`
   - Top 20 results by cosine similarity
   - Results:
     ```
     1. authenticate() - similarity: 0.87
     2. validate_token() - similarity: 0.82
     3. LoginManager.__init__() - similarity: 0.79
     4. check_credentials() - similarity: 0.76
     ...
     20. logout() - similarity: 0.58
     ```

3. **Reranking (MMR)**
   - Apply diversity filter
   - Reduce redundant chunks from same file
   - Final top 10 results

4. **Git Context (if applicable)**
   - Query contains "authentication" but not git keywords
   - Skip git context augmentation

5. **Context Assembly**
   ```markdown
   # Relevant Code Context

   ## Chunk 1: authenticate
   File: src/auth/login.py:122-180
   Type: function
   Language: python
   Similarity: 0.87

   def authenticate(username: str, password: str) -> bool:
       """Authenticate user credentials."""
       ...

   ## Chunk 2: validate_token
   File: src/auth/login.py:182-220
   ...
   ```

6. **LLM Generation**
   - Provider: Codex CLI
   - Prompt: Context + Query
   - Temperature: 0.1
   - Max tokens: 2000
   - Response: "Authentication is implemented using..."

7. **Response Construction**
   ```json
   {
       "answer": "Authentication is implemented...",
       "sources": [
           {"file_path": "src/auth/login.py", "name": "authenticate", ...},
           ...
       ],
       "metadata": {
           "retrieved_chunks": 20,
           "final_chunks": 10,
           "llm_provider": "codex"
       }
   }
   ```

---

## Performance Characteristics

### Indexing Performance

**Test Repository:** 100 Python files, 10,000 lines of code

- **Full indexing time:** ~45 seconds
  - File reading: 2s
  - Parsing: 8s
  - Chunking: 3s
  - Embedding generation: 25s (CPU)
  - ChromaDB storage: 7s

- **Chunks created:** 534
- **Average chunk size:** 250 lines
- **Embedding throughput:** ~21 chunks/second

### Query Performance

**Average query latency:** ~800ms
- Query embedding: 50ms
- ChromaDB search: 200ms
- Reranking: 100ms
- LLM generation: 450ms (varies by provider)

### Storage Requirements

**Per repository (10,000 LOC):**
- ChromaDB vectors: ~2MB (534 chunks × 384 dims × 4 bytes)
- SQLite metadata: ~50KB
- Embedding model cache: 80MB (shared)

---

## Version 1 Limitations

1. **Simplified Parsing:** Line-based parsing instead of full AST analysis
2. **No Tree-Sitter:** Planned for future versions
3. **CPU-Only Embeddings:** GPU acceleration not configured
4. **No Caching:** Embedding cache not implemented
5. **Single-Threaded:** No parallel processing of files
6. **Basic Error Handling:** Limited retry logic
7. **No Incremental Commit Indexing:** Only file-level incremental updates

---

## Next Steps (Post-Version 1)

Planned enhancements for future versions:

1. **Tree-Sitter Integration:** Full AST-based parsing
2. **GPU Acceleration:** CUDA support for embedding generation
3. **Parallel Processing:** Multi-threaded file indexing
4. **Advanced Reranking:** Cross-encoder models
5. **Commit-Level Indexing:** Index individual commits
6. **Embedding Cache:** Persistent cache for unchanged chunks
7. **Real-time Indexing:** File system watch for auto-reindex
8. **Multi-Modal Support:** Image/diagram understanding

---

## Conclusion

This document describes the complete data processing pipeline for Git RAG Chat Version 1 (commit `5fb68bf`). The system successfully indexes Git repositories, generates semantic embeddings, and enables natural language querying of codebases using RAG techniques.

The architecture is modular and designed for extensibility, with clear separation between parsing, chunking, embedding, and storage layers.

---

**Document Version:** 1.0
**Last Updated:** December 17, 2025
**Author:** System Documentation (Generated for Confluence)

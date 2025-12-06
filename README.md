# Git RAG Chat - Local Repository Code Analysis

A Docker-based RAG (Retrieval-Augmented Generation) chatbot system that tracks Git changes (committed and uncommitted) and enables natural language querying of code repositories using ChromaDB for vector storage.

## Features

- **Multi-Repository Support**: Track multiple Git repositories with persistent vector indexes
- **Real-Time Change Tracking**: Monitor both committed and uncommitted changes
- **Intelligent Code Parsing**: AST-based semantic chunking using tree-sitter
- **LLM Integration**: Codex CLI with ChatGPT Enterprise (GPT-4) support
- **Directory Picker UI**: Gradio web interface for easy repository selection
- **Fully Containerized**: Docker Compose deployment for easy setup

## Development Status

### ✅ Phase 1, 2 & 3: Core Pipeline Complete

**Phase 1** (Foundation):

- ✅ Project structure created
- ✅ Docker Compose configuration
- ✅ SQLite metadata database
- ✅ Configuration management
- ✅ FastAPI application skeleton with API routes

**Phase 2** (Git & Parsing):

- ✅ GitPython integration for commit history
- ✅ tree-sitter code parser (Python, JavaScript, TypeScript)
- ✅ Chunking strategies (AST-based + fixed-size)
- ✅ File tracking and validation

**Phase 3** (Embedding & Vector Store):

- ✅ ChromaDB integration with collection management
- ✅ sentence-transformers embedding generation
- ✅ Repository indexing orchestration
- ✅ Full/incremental indexing support
- ✅ File-level indexing and re-indexing
- ✅ Vector search and metadata filtering

**Phase 4** (File Watcher):

- ✅ watchdog-based file system monitoring
- ✅ Debounced file change detection (2-second default)
- ✅ Git commit monitoring with polling
- ✅ Automatic incremental indexing on changes
- ✅ Integration with RAG pipeline API

### 📅 Next Steps: Phase 5-8

See the [implementation plan](.claude/plans/golden-popping-iverson.md) for full details.

## Quick Start

```bash
# 1. Install Codex CLI and authenticate with ChatGPT Enterprise
codex auth login

# 2. Copy environment file
cp .env.example .env

# 3. Start services
docker-compose up --build

# 4. Access the UI
open http://localhost:7860
```

## Documentation

For full setup instructions, architecture details, and API documentation, see:

- [Implementation Plan](.claude/plans/golden-popping-iverson.md)
- API Docs: <http://localhost:8001/docs> (when running)

## Technology Stack

- **Vector DB**: ChromaDB
- **Embedding**: sentence-transformers
- **LLM**: Codex CLI (ChatGPT Enterprise)
- **API**: FastAPI + Python 3.11
- **UI**: Gradio (Phase 7)

---

**Current Status**: Phase 1 & 2 Complete | Ready for Phase 3 (Embedding & Vector Store)

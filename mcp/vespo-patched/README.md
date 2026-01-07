# ChromaDB MCP Server - PATCHED for Codex CLI 🔧

> **MCP-Compliant version of vespo92/chromadblocal-mcp-server**
> Fixed for ChatGPT Codex CLI stdio protocol requirements

[![MCP](https://img.shields.io/badge/MCP-Protocol%20Compliant-green)](https://modelcontextprotocol.io)
[![Codex CLI](https://img.shields.io/badge/Codex%20CLI-Compatible-blue)](https://github.com/anthropics/claude-code)
[![Version](https://img.shields.io/badge/version-3.0.1--patched-orange)](https://github.com/vespo92/chromadblocal-mcp-server)

## 🎯 What is This?

This is a **fully patched and tested** version of the excellent [vespo92/chromadblocal-mcp-server](https://github.com/vespo92/chromadblocal-mcp-server) that **works correctly with ChatGPT Codex CLI** in VS Code.

### Why Was This Patch Needed?

The original vespo92 server is feature-rich with 22 advanced tools, but had **MCP stdio protocol compliance issues** that prevented it from working with Codex CLI:

1. ❌ `console.error()` calls contaminated stdio during handshake
2. ❌ Startup banner printed during MCP initialization
3. ❌ Progress logs interfered with JSON-RPC messages
4. ❌ Bun runtime could inject stdout noise

### What Did We Fix?

✅ **All `console.error()` wrapped in `DEBUG_MCP` flag**
✅ **Removed startup banners and progress logs**
✅ **Clean Dockerfile using direct `bun index.js`** (not `bun run`)
✅ **Stdio-compliant handshake for Codex CLI**
✅ **Preserves all 22 advanced tools from original**

---

## 🚀 Features (All Preserved!)

### Core MCP Tools
- ✅ `search_context` - Vector search across collections
- ✅ `store_context` - Store documents with metadata
- ✅ `list_collections` - List local/remote collections
- ✅ `find_similar_patterns` - Find similar code patterns
- ✅ `get_environment` - Environment routing info

### 🗂️ Batch File Processing (vespo92's killer feature!)
- ✅ `scan_directory` - Preview files before ingesting
- ✅ `batch_ingest` - Bulk ingest 500+ files with metadata
- ✅ `quick_load` - Fast temporary collection loading
- ✅ `unload_collection` - Clean up temp collections
- ✅ `export_collection` - Backup to JSON
- ✅ `import_collection` - Restore from JSON
- ✅ `batch_delete` - Delete by IDs or filters
- ✅ `get_collection_info` - Collection statistics
- ✅ `ingest_file` - Single file ingestion
- ✅ `list_file_types` - Show 77 supported file types

### 📸 Photo & EXIF Tools
- ✅ `extract_exif` - Camera, lens, GPS, date extraction

### 👁️ Watch Folder Tools
- ✅ `watch_folder` - Auto-ingest new files
- ✅ `stop_watch` - Stop watching
- ✅ `list_watchers` - List active watchers

### 🔍 Duplicate Detection
- ✅ `find_duplicates` - Find duplicate files by hash
- ✅ `compare_files` - Compare two files
- ✅ `find_collection_duplicates` - Find dupes in collection

**77 file types supported**: Photos (.jpg, .png, .raw, .heic), CAD (.stl, .obj, .dxf), Documents (.pdf, .docx), Data (.json, .yaml), Code (.js, .py, .rs, etc.)

---

## 📦 Quick Setup (One Command)

### Prerequisites
- [Docker Desktop](https://docker.com) (running)
- [Codex CLI](https://github.com/anthropics/claude-code) installed
- Windows PowerShell (for setup script)

### Installation

1. **Run the setup script:**
   ```powershell
   cd mcp\vespo-patched
   .\setup-codex-vespo.ps1
   ```

2. **Follow the prompts:**
   - Enter your repository path when asked
   - Script will:
     - Start ChromaDB (Docker)
     - Build the patched MCP server
     - Configure Codex CLI
     - Test the handshake

3. **Restart VS Code completely** (important!)

4. **Test in Codex:**
   ```
   You: List chroma collections
   You: Scan directory /workspace
   You: Quick load /workspace into temp_repo
   You: Search for authentication in temp_repo
   You: Unload collection temp_repo
   ```

---

## 🔧 Manual Setup (Alternative)

If you prefer manual setup or need more control:

### 1. Start ChromaDB

```bash
docker network create chroma-net

docker run -d \
  --name chromadb-local \
  --network chroma-net \
  -p 8001:8000 \
  chromadb/chroma:latest
```

### 2. Build the Patched MCP Server

```bash
cd mcp/vespo-patched
docker build -t chroma-mcp-vespo-patched:latest .
```

### 3. Configure Codex CLI

Edit `~/.codex/config.toml`:

```toml
[mcp_servers.chromadb_context_vespo]
command = "docker"
args = [
  "run", "--rm", "-i",
  "--network", "chroma-net",
  "-e", "CHROMA_URL=http://chromadb-local:8000",
  "-e", "CHROMADB_URL=http://chromadb-local:8000",
  "-v", "/c/your/repo:/workspace:ro",  # CHANGE THIS!
  "-w", "/workspace",
  "chroma-mcp-vespo-patched:latest"
]
startup_timeout_sec = 45
tool_timeout_sec = 180
enabled = true
```

### 4. Verify

```bash
codex mcp list
```

You should see `chromadb_context_vespo` in the list.

---

## 🧪 Testing & Validation

### Test MCP Handshake (Manual)

```bash
docker run --rm -i \
  --network chroma-net \
  -e CHROMA_URL=http://chromadb-local:8000 \
  chroma-mcp-vespo-patched:latest
```

Then paste (line by line):
```json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0.0"}}}
{"jsonrpc":"2.0","method":"notifications/initialized"}
{"jsonrpc":"2.0","id":2,"method":"tools/list"}
```

**Expected:** Clean JSON-RPC responses (no extra text before `{`)

### Test in Codex CLI

1. Restart VS Code
2. Open a new Codex chat
3. Try:
   ```
   List all MCP tools available for chromadb_context_vespo
   ```

---

## 📋 Key Differences vs. Official Chroma MCP

| Feature | Official `mcp/chroma` | Patched Vespo Server |
|---------|----------------------|---------------------|
| **Basic CRUD** | ✅ 11 tools | ✅ Same |
| **Batch Processing** | ❌ None | ✅ 10 tools (500+ files) |
| **EXIF Extraction** | ❌ None | ✅ Camera, GPS, date |
| **Watch Folders** | ❌ None | ✅ Auto-ingest |
| **Duplicate Detection** | ❌ None | ✅ Hash-based |
| **77 File Types** | ❌ Manual only | ✅ Auto-processed |
| **Codex CLI Compatible** | ✅ Yes (Python) | ✅ Yes (patched) |
| **Runtime** | Python/uv | Bun/Node |

---

## 🐛 Debugging

### Enable Debug Logging

Set `DEBUG_MCP=true` to see internal logs (only to stderr):

```toml
[mcp_servers.chromadb_context_vespo]
command = "docker"
args = [
  "run", "--rm", "-i",
  "--network", "chroma-net",
  "-e", "DEBUG_MCP=true",          # <-- Add this
  "-e", "CHROMA_URL=http://chromadb-local:8000",
  ...
]
```

### Common Issues

**Problem:** "handshaking with MCP server failed"

**Solution:**
1. Ensure Docker Desktop is running
2. Verify ChromaDB is accessible: `curl http://localhost:8001/api/v2/heartbeat`
3. Check Docker network: `docker network inspect chroma-net`
4. Check logs: `codex mcp logs chromadb_context_vespo`

**Problem:** Server starts but tools not available

**Solution:**
1. Completely quit VS Code (not just reload)
2. Ensure `enabled = true` in config.toml
3. Start a **new** Codex chat (old chats won't see new MCPs)

---

## 📝 Example Workflows

### Index a Codebase

```
You: Scan directory /workspace to preview files
AI: [Shows stats: 450 .js files, 120 .py files, etc.]

You: Batch ingest /workspace into collection my_codebase (max 500 files, categories: code)
AI: [Ingests 500 files in ~10 seconds]

You: Search for authentication middleware in my_codebase
AI: [Returns relevant code snippets with metadata]
```

### Process Photo Library

```
You: Quick load ~/Photos/Vacation2024 (categories: images)
AI: [Creates temp_1234567, loads 200 photos with EXIF]

You: Find photos taken with Canon in temp_1234567
AI: [Returns matching photos with camera metadata]

You: Extract EXIF from /home/photos/IMG_1234.jpg
AI: [Returns camera, lens, exposure, GPS coordinates]

You: Unload collection temp_1234567
AI: [Cleans up]
```

### Find Duplicate Files

```
You: Find duplicates in ~/Downloads (recursive: true, hash_method: partial)
AI: [Scans 2000 files, finds 15 duplicate groups wasting 2.3 GB]

You: Compare files ~/file1.jpg and ~/file2.jpg
AI: [Byte-by-byte comparison result]
```

---

## 🏗️ Architecture

```
┌─────────────────┐
│   Codex CLI     │
│   (VS Code)     │
└────────┬────────┘
         │ stdio (JSON-RPC)
         │
┌────────▼────────────────────┐
│  Patched Vespo MCP Server   │
│  (Docker: Bun + Node)        │
│  - 22 Tools                  │
│  - Stdio Compliant           │
│  - No stderr contamination   │
└────────┬────────────────────┘
         │ HTTP
         │
┌────────▼────────────┐
│    ChromaDB         │
│  (Docker: port 8001)│
│  - Vector Storage   │
│  - Embeddings       │
└─────────────────────┘
```

---

## 🔍 What We Changed (Technical)

### 1. Patched `index.js`

**Before:**
```javascript
console.error(`🔍 Searching in ${route} ChromaDB`);
console.error(`📁 Scanning ${dirPath}...`);
```

**After:**
```javascript
const DEBUG = process.env.DEBUG_MCP === 'true';
function debugLog(...args) {
  if (DEBUG) console.error('[MCP-DEBUG]', ...args);
}
debugLog(`Searching in ${route} ChromaDB`);
```

### 2. Fixed Startup (Line 1543)

**Before:**
```javascript
console.error('ChromaDB Context MCP server v3.0.0 running - EXIF, Watch Folders, Duplicate Detection enabled');
```

**After:**
```javascript
// CRITICAL: No startup messages during handshake!
// Only enable with DEBUG_MCP=true
```

### 3. Clean Dockerfile

**Before:**
```dockerfile
CMD ["bun","run","index.js"]  # Can inject "bun run" banners
```

**After:**
```dockerfile
CMD ["bun","index.js"]  # Direct execution, zero stdout noise
```

---

## 🙏 Credits

- **Original Server:** [vespo92/chromadblocal-mcp-server](https://github.com/vespo92/chromadblocal-mcp-server) - Amazing feature set!
- **Fixes & Patches:** Applied for Codex CLI compatibility
- **MCP Protocol:** [Anthropic Model Context Protocol](https://modelcontextprotocol.io)
- **ChromaDB:** [Chroma Vector Database](https://www.trychroma.com)

---

## 📄 License

Inherits MIT License from [vespo92/chromadblocal-mcp-server](https://github.com/vespo92/chromadblocal-mcp-server)

---

## ❓ FAQ

### Q: Why not just use the official `mcp/chroma` server?

**A:** The official server is excellent for basic CRUD but lacks:
- Batch file processing (500+ files)
- EXIF extraction
- Watch folders
- Duplicate detection
- Support for 77 file types

This patched version gives you **both** Codex compatibility **and** advanced features.

### Q: Can I use this with Claude Desktop?

**A:** Yes! Just use the Bun command instead of Docker:

```json
{
  "mcpServers": {
    "chromadb-vespo": {
      "command": "bun",
      "args": ["run", "/path/to/vespo-patched/index.js"],
      "env": {
        "CHROMA_URL": "http://localhost:8001"
      }
    }
  }
}
```

### Q: Does this work on Linux/Mac?

**A:** Yes! Just adapt the setup script:
- Use bash instead of PowerShell
- Adjust Docker volume paths (already using `/c/...` format)

### Q: Can I contribute improvements?

**A:** Absolutely! Fork this repo and submit PRs. Key areas:
- Better error handling
- More file type support
- Performance optimizations

---

## 🎉 Success!

If you see this working in Codex CLI, congrats! You now have:
- ✅ ChatGPT with persistent memory via ChromaDB
- ✅ 22 advanced MCP tools for file processing
- ✅ Batch indexing of entire codebases
- ✅ Photo EXIF extraction and search
- ✅ Watch folder auto-ingestion
- ✅ Duplicate file detection

**Enjoy building with MCP! 🚀**

---

*For issues specific to the patching, open an issue in this repo.*
*For issues with the original features, see [vespo92's repo](https://github.com/vespo92/chromadblocal-mcp-server).*

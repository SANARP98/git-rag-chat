# 🚀 Quick Start Guide - Patched Vespo ChromaDB MCP Server

> Get up and running in 5 minutes!

---

## Prerequisites Check

Before starting, make sure you have:

- [ ] Docker Desktop installed and **running**
- [ ] Codex CLI installed (`codex --version` works)
- [ ] Windows PowerShell (for setup script)

---

## Step-by-Step Setup

### 1️⃣ Navigate to the Patched Directory

```powershell
cd mcp\vespo-patched
```

### 2️⃣ Run the Setup Script

```powershell
.\setup-codex-vespo.ps1
```

### 3️⃣ Enter Your Repo Path

When prompted, enter the full path to your repository:
```
Enter your repo path: C:\Users\you\source\myrepo
```

### 4️⃣ Wait for Setup to Complete

The script will:
- ✅ Check prerequisites
- ✅ Create Docker network (`chroma-net`)
- ✅ Start ChromaDB container on port 8001
- ✅ Build the patched MCP server image
- ✅ Update Codex CLI config (`~/.codex/config.toml`)
- ✅ Validate the setup

**Expected output:**
```
=== [9/10] Setup Complete! ===

Configuration Summary:
  - ChromaDB:       http://localhost:8001
  - Docker network: chroma-net
  - MCP Server:     chromadb_context_vespo
  - Repo mounted:   /workspace (read-only)
```

### 5️⃣ Restart VS Code

**IMPORTANT:** You must **completely close** VS Code and reopen it!

- Don't just "Reload Window"
- Exit VS Code entirely (Ctrl+Q or File → Exit)
- Reopen VS Code

### 6️⃣ Test in Codex

1. Open your repository in VS Code
2. Start a **new** Codex chat (Ctrl+Shift+P → "Codex: New Chat")
3. Try these commands:

```
List all MCP servers
```

You should see `chromadb_context_vespo` in the list.

```
List chroma collections
```

Should return empty list or existing collections.

```
Scan directory /workspace
```

Should show file statistics from your repo.

---

## 🎯 First Real Task: Index Your Codebase

Once setup is working:

```
You: Scan directory /workspace to see what files we have
```

Wait for stats, then:

```
You: Batch ingest /workspace into collection my_codebase
    - Max 500 files
    - Categories: code
    - Include content: true
```

Wait ~10 seconds for ingestion, then:

```
You: Search for "authentication" in my_codebase collection
```

You should get relevant code snippets with metadata!

---

## 🐛 Troubleshooting

### Issue: "Command 'codex' not found"

**Solution:** Install Codex CLI first
```bash
npm install -g @anthropics/claude-code
```

### Issue: "Docker not found"

**Solution:**
1. Install Docker Desktop
2. Make sure it's running (check system tray)
3. Test: `docker ps` should work

### Issue: "Port 8001 already in use"

**Solution:** The script will auto-find a free port, but if it fails:
```bash
docker ps -a
docker rm -f chromadb-local
```

### Issue: "Setup completes but tools don't appear in Codex"

**Solution:**
1. Did you restart VS Code **completely**?
2. Did you start a **new** chat (old chats don't see new servers)?
3. Check config: `codex mcp list`
4. Check logs: `codex mcp logs chromadb_context_vespo`

### Issue: "Handshake timeout"

**Solution:**
1. Check ChromaDB is running:
   ```bash
   curl http://localhost:8001/api/v2/heartbeat
   ```
2. Check Docker network:
   ```bash
   docker network inspect chroma-net
   ```
3. Check MCP server can reach ChromaDB:
   ```bash
   docker run --rm --network chroma-net alpine ping chromadb-local
   ```

---

## 📚 What's Available?

### 22 MCP Tools Installed:

#### Core Tools (5)
- `search_context` - Vector search
- `store_context` - Store documents
- `list_collections` - List collections
- `find_similar_patterns` - Code pattern search
- `get_environment` - Environment info

#### Batch Processing (10)
- `scan_directory` - Preview files
- `batch_ingest` - Bulk ingest
- `quick_load` - Fast temp load
- `unload_collection` - Clean up
- `export_collection` - Backup
- `import_collection` - Restore
- `batch_delete` - Delete many
- `get_collection_info` - Stats
- `ingest_file` - Single file
- `list_file_types` - Show supported types

#### Photo Tools (1)
- `extract_exif` - Camera/GPS/date extraction

#### Watch Folders (3)
- `watch_folder` - Auto-ingest
- `stop_watch` - Stop watching
- `list_watchers` - List active

#### Duplicate Detection (3)
- `find_duplicates` - Find dupes
- `compare_files` - Compare two
- `find_collection_duplicates` - Check collection

---

## 🎮 Example Commands

### Index Your Entire Repo
```
Quick load /workspace into collection temp_repo (max 500 files, categories: code)
```

### Search Code
```
Search for "API endpoint" in temp_repo collection
```

### Find Duplicates
```
Find duplicates in /workspace (recursive: true, hash_method: partial)
```

### Process Photos
```
Quick load ~/Photos (categories: images)
```

### Watch a Folder
```
Watch folder ~/Downloads for new files, auto-ingest to collection auto_files
```

---

## 📊 Performance Expectations

| Operation | File Count | Time |
|-----------|-----------|------|
| Scan directory | 1000 files | 2-3 sec |
| Quick load | 200 files | 2-3 sec |
| Batch ingest | 500 files | 5-10 sec |
| Search | Any | <1 sec |
| Find duplicates | 2000 files | 10-20 sec |

---

## 🔧 Advanced: Enable Debug Logging

If you need to troubleshoot, enable debug logs:

Edit `~/.codex/config.toml`:

```toml
[mcp_servers.chromadb_context_vespo]
command = "docker"
args = [
  "run", "--rm", "-i",
  "--network", "chroma-net",
  "-e", "DEBUG_MCP=true",          # <-- Add this line
  "-e", "CHROMA_URL=http://chromadb-local:8000",
  ...rest of config...
]
```

Restart Codex, and logs will appear in:
```bash
codex mcp logs chromadb_context_vespo
```

---

## 🎉 Success Indicators

You'll know it's working when:

✅ `codex mcp list` shows `chromadb_context_vespo`
✅ Codex chat responds to "List chroma collections"
✅ Scanning/ingesting files completes without errors
✅ Search returns relevant results
✅ No "handshake failed" errors

---

## 📖 Next Steps

Once you have it working:

1. **Read the full README:** [vespo-patched/README.md](vespo-patched/README.md)
2. **Try batch processing:** Index your entire codebase
3. **Explore EXIF tools:** Process photo libraries
4. **Set up watch folders:** Auto-ingest downloads
5. **Find duplicates:** Clean up your filesystem

---

## 💡 Pro Tips

- **Use quick_load for temp work** (fast, auto-cleanup)
- **Use batch_ingest for permanent** (slower, stays in DB)
- **Always unload_collection** after quick_load to save memory
- **Export collections** regularly as JSON backups
- **Enable DEBUG_MCP** only when troubleshooting (verbose!)

---

## 🆘 Still Stuck?

Check these in order:

1. **Docker running?** `docker ps` should work
2. **Codex installed?** `codex --version` should work
3. **Config updated?** `codex mcp list` should show server
4. **VS Code restarted?** Completely, not just reload
5. **New chat?** Old chats don't see new servers
6. **Logs?** `codex mcp logs chromadb_context_vespo`

If all else fails, review:
- [PATCHING_SUMMARY.md](PATCHING_SUMMARY.md) - Technical details
- [vespo-patched/README.md](vespo-patched/README.md) - Full docs

---

**🚀 Ready to build with persistent AI memory? Let's go!**

# Codex CLI MCP Troubleshooting Guide

## Issue: "No MCP servers returned any resources"

When you see this message in Codex:
```
• No MCP servers returned any resources in this session.
```

This doesn't mean the servers aren't configured - it means something else.

---

## Understanding MCP: Resources vs Tools

MCP servers can provide two types of capabilities:

### **Resources**
- File-like data that can be read
- Examples: documents, knowledge bases, file contents
- Listed with `list_resources` method

### **Tools**
- Functions that can be called
- Examples: search, ingest, query
- Listed with `tools/list` method

**Our vespo server provides TOOLS, not RESOURCES!**

---

## The Real Issue

When Codex starts, it:
1. Tries to connect to MCP server ✅
2. Sends `initialize` request
3. Waits for `initialize` response
4. **Fails here** ← This is where it's breaking

The error you saw earlier:
```
⚠ MCP client for `chromadb_context_vespo` failed to start:
  MCP startup failed: handshaking with MCP server failed:
  connection closed: initialize response
```

This means the server is **not responding to the initialize request** when Codex calls it.

---

## Why It Works Manually But Not in Codex

### Manual Test ✅
```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize",...}' | docker run ...
```
- Single request/response
- Direct stdio
- No timeout issues

### Codex CLI ❌
```
Codex starts → Spawns docker run → Waits for response → TIMEOUT
```
- More complex lifecycle
- Multiple messages expected
- Strict timing requirements
- Git Bash path conversion issues

---

## Root Cause: Git Bash Path Conversion

When Codex CLI (running in Git Bash on Windows) executes:
```bash
docker run ... -v "/c/Users/.../git-rag-chat://workspace:ro" ...
```

Git Bash converts paths starting with `/` to Windows paths, causing:
- `/workspace` → `C:/Program Files/Git/workspace` (doesn't exist!)
- Server fails to start properly
- No response to initialize

---

## Solution: Use PowerShell, Not Git Bash

The issue is that **Codex CLI is running in Git Bash context** on Windows.

### Option 1: Run Codex from PowerShell (Recommended)

```powershell
# Close current Git Bash codex session
# Open PowerShell
cd "C:\Users\prenganathan\OneDrive - Adaptive Biotechnologies\Documents\git-rag-chat\git-rag-chat"
codex
```

### Option 2: Use MSYS2_ARG_CONV_EXCL

Set this environment variable in Git Bash:
```bash
export MSYS2_ARG_CONV_EXCL="*"
codex
```

This tells Git Bash to NOT convert paths.

### Option 3: Use WSL (Windows Subsystem for Linux)

If you have WSL installed:
```bash
wsl
cd /mnt/c/Users/prenganathan/...
codex
```

---

## Verification Steps

### 1. Check Which Shell You're Using

```bash
echo $SHELL
```

- If `/bin/bash` or `/usr/bin/bash` → **Git Bash** (problematic)
- If shows PowerShell path → **PowerShell** (good)
- If `/bin/zsh` or similar → **WSL/Linux** (good)

### 2. Test Docker Command Directly

From your current shell:
```bash
docker run --rm alpine pwd
```

- If shows `/` → Good
- If shows `C:/...` → Git Bash is converting paths

### 3. Check Codex Startup Location

```bash
codex
# Look at the directory line:
# directory: ~\…\Documents\git-rag-chat\git-rag-chat
```

- If shows `\` (backslashes) → PowerShell context
- If shows `/` (forward slashes) → Bash context

---

## Recommended Fix: Update Config for PowerShell

Edit `~/.codex/config.toml` and change the volume mount:

### Current (Git Bash style):
```toml
"-v","/c/Users/prenganathan/OneDrive - Adaptive Biotechnologies/Documents/git-rag-chat/git-rag-chat://workspace:ro",
```

### Change to (PowerShell/Windows style):
```toml
"-v","C:\\Users\\prenganathan\\OneDrive - Adaptive Biotechnologies\\Documents\\git-rag-chat\\git-rag-chat:/workspace:ro",
```

**Note:**
- Use Windows path with `\\` (escaped backslashes)
- Single `:` before `/workspace` (not `://`)
- Remove the double slash

---

## Quick Fix Script

Run this PowerShell script to fix the config:

```powershell
$configPath = "$env:USERPROFILE\.codex\config.toml"
$config = Get-Content $configPath -Raw

# Fix the volume mount path
$config = $config -replace '"-v","/c/Users/([^"]+)://workspace:ro"', '"-v","C:\\Users\\$1:/workspace:ro"'

Set-Content $configPath -Value $config -Encoding UTF8

Write-Host "Config fixed! Restart Codex from PowerShell."
```

---

## Testing After Fix

1. **Close Git Bash**
2. **Open PowerShell**
3. **Navigate to your project:**
   ```powershell
   cd "C:\Users\prenganathan\OneDrive - Adaptive Biotechnologies\Documents\git-rag-chat\git-rag-chat"
   ```
4. **Start Codex:**
   ```powershell
   codex
   ```
5. **Test:**
   ```
   List all available tools
   ```

---

## Expected Success Output

```
╭────────────────────────────────────────────────────╮
│ >_ OpenAI Codex (v0.79.0)                          │
╰────────────────────────────────────────────────────╯

› List all available tools

• Found 22 tools from chromadb_context_vespo:
  - search_context
  - store_context
  - batch_ingest
  - quick_load
  - extract_exif
  ... etc
```

---

## If Still Not Working

### Check Codex CLI Version
```bash
codex --version
```

Ensure you're on v0.79.0 or later.

### Check Docker Desktop
```bash
docker ps
```

Ensure ChromaDB containers are running.

### Manually Test Server Startup
```powershell
docker run --rm -i `
  --network chroma-net `
  -e CHROMA_URL=http://chromadb-vespo:8000 `
  -e CHROMADB_URL=http://chromadb-vespo:8000 `
  -v "C:\Users\prenganathan\OneDrive - Adaptive Biotechnologies\Documents\git-rag-chat\git-rag-chat:/workspace:ro" `
  chroma-mcp-vespo-patched:latest
```

Then paste:
```json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0.0"}}}
```

Should return JSON response immediately.

---

## Summary

**Problem:** Git Bash converts Docker paths, breaking MCP server startup
**Solution:** Run Codex from PowerShell, not Git Bash
**Fix:** Update config.toml to use Windows paths with proper escaping

**Bottom line: The MCP server works fine - it's just a shell/path issue!**

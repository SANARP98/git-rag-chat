# Final Setup Script - Complete Solution

## 🎯 File: `setup-codex-vespo-final.ps1`

This is the **ultimate, battle-tested version** of the setup script that incorporates ALL fixes discovered during troubleshooting.

---

## ✨ What Makes This "Final"?

### All Critical Fixes Included:

1. ✅ **PowerShell-Compatible Paths**
   - Uses `C:\\Users\\...` (Windows format with escaped backslashes)
   - NOT `/c/Users/...` (Git Bash format that breaks)
   - Single colon: `:/workspace` (not `://workspace`)

2. ✅ **Removed `-w` Flag**
   - The working directory flag was causing "connection closed" errors
   - Container now uses default `/app` directory (where code lives)
   - Workspace still mounted at `/workspace` for file access

3. ✅ **Intelligent Port Selection**
   - Finds free ports starting from 8003
   - Won't conflict with existing ChromaDB instances
   - Updates config with correct port

4. ✅ **Path Space Handling**
   - Properly escapes paths with spaces
   - Works with paths like `C:\Users\John Doe\Documents`
   - TOML-compliant escaping

5. ✅ **GitHub Clone Integration**
   - Clones from https://github.com/SANARP98/git-rag-chat
   - Asks for installation directory
   - Handles existing repos gracefully

6. ✅ **Comprehensive Validation**
   - Tests prerequisites
   - Validates Docker is running
   - Tests MCP handshake before finalizing
   - Verifies ChromaDB startup

---

## 🔧 Key Technical Changes

### Config Generation (The Critical Fix)

**OLD (Broken):**
```toml
args = [
  "run","--rm","-i",
  "-v","/c/Users/name/path://workspace:ro",  # Git Bash format ❌
  "-w","/workspace",                          # Causes handshake failure ❌
  "image"
]
```

**NEW (Fixed):**
```toml
args = [
  "run","--rm","-i",
  "-v","C:\\Users\\name\\path:/workspace:ro",  # Windows format ✅
  "image"                                       # No -w flag ✅
]
```

### Why These Changes?

1. **Git Bash Path Conversion**
   - When Codex runs from Git Bash, paths like `/c/Users/...` get converted
   - PowerShell format `C:\\...` works in both environments
   - Proper TOML escaping prevents parsing errors

2. **Working Directory Issue**
   - `-w /workspace` was converted to Windows path by Git Bash
   - This path doesn't exist in container
   - Server fails to start, handshake never completes
   - **Solution:** Remove `-w`, let container use `/app` (default from Dockerfile)

3. **Double Slash Problem**
   - `://workspace` was used to prevent Git Bash conversion
   - Not needed with Windows format
   - Single `:` is correct Docker syntax

---

## 🚀 How to Use

### Quick Start

```powershell
cd mcp\vespo-patched
.\setup-codex-vespo-final.ps1
```

### What It Will Do

1. ✅ Check prerequisites (Docker, codex, git)
2. ✅ Ask where to install (handles spaces correctly)
3. ✅ Clone git-rag-chat from GitHub
4. ✅ Create Docker network
5. ✅ Find free port (8003+)
6. ✅ Start ChromaDB container
7. ✅ Build patched MCP server image
8. ✅ Test MCP handshake
9. ✅ **Generate PowerShell-compatible config**
10. ✅ Verify registration
11. ✅ Show comprehensive summary
12. ✅ Guide you through next steps

### Expected Output

```
╔═══════════════════════════════════════════════════════════════════╗
║  Patched Vespo ChromaDB MCP Server Setup for Codex CLI (FINAL)   ║
║  - Fixes stdio handshake issues                                   ║
║  - Generates PowerShell-compatible paths                          ║
║  - Removes -w flag that causes failures                           ║
╚═══════════════════════════════════════════════════════════════════╝

==> [1/12] Checking prerequisites...
✓ All prerequisites found (codex, docker, git)
✓ Docker Desktop is running

==> [2/12] Getting installation directory...
...

==> [12/12] Setup Complete!
╔════════════════════════════════════════════════════════════════════╗
║                    SETUP SUCCESSFUL ✓                              ║
╚════════════════════════════════════════════════════════════════════╝

🎯 Key Fixes Applied:
✓ PowerShell-compatible paths (not Git Bash /c/ format)
✓ Removed -w flag (was causing handshake failures)
✓ Proper TOML escaping for paths with spaces
✓ Auto-selected free port (8003)
✓ Tested MCP handshake before finalizing
```

---

## 📋 Generated Config Example

The script generates this config (with your actual paths):

```toml
# Patched vespo92 ChromaDB MCP server (22 advanced tools + batch processing)
# Auto-configured by setup script on 2026-01-08 12:34:56
# IMPORTANT: This config uses PowerShell-compatible paths (not Git Bash paths)
[mcp_servers.chromadb_context_vespo]
command = "docker"
args = [
  "run","--rm","-i",
  "--network","chroma-net",
  "-e","CHROMA_URL=http://chromadb-vespo:8000",
  "-e","CHROMADB_URL=http://chromadb-vespo:8000",
  "-v","C:\\Users\\prenganathan\\Documents\\git-rag-chat:/workspace:ro",
  "chroma-mcp-vespo-patched:latest"
]
startup_timeout_sec = 45
tool_timeout_sec = 180
enabled = true
```

**Note the critical differences:**
- ✅ Windows path: `C:\\Users\\...`
- ✅ Escaped backslashes: `\\`
- ✅ Single colon: `:/workspace`
- ✅ **NO** `-w` flag

---

## 🎯 Why This Version Is "Final"

### Incorporates ALL Lessons Learned:

1. **Issue:** Git Bash converts paths
   - **Solution:** Use Windows format with escaped backslashes

2. **Issue:** `-w /workspace` causes handshake failure
   - **Solution:** Remove `-w` flag completely

3. **Issue:** Paths with spaces break
   - **Solution:** Proper TOML escaping function

4. **Issue:** Port conflicts
   - **Solution:** Smart port finding

5. **Issue:** Manual process
   - **Solution:** Fully automated from GitHub clone to config

6. **Issue:** Hard to debug
   - **Solution:** Comprehensive logging and validation

7. **Issue:** Works manually but not in Codex
   - **Solution:** Match exact config format Codex expects

---

## 🧪 Testing Checklist

After running the script:

### 1. Verify Config
```powershell
cat ~/.codex/config.toml | Select-String -Pattern "chromadb_context_vespo" -Context 0,10
```

Should show Windows-style paths, no `-w` flag.

### 2. Check Containers
```bash
docker ps --filter "name=chroma"
```

Should show:
- `chromadb-local` (your original, if exists)
- `chromadb-vespo` (new patched version)

### 3. Test Handshake
```powershell
docker run --rm -i `
  --network chroma-net `
  -e CHROMA_URL=http://chromadb-vespo:8000 `
  chroma-mcp-vespo-patched:latest
```

Paste:
```json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0.0"}}}
```

Should return JSON immediately.

### 4. Test in Codex

**IMPORTANT:** Must run from PowerShell!

```powershell
cd "C:\Users\prenganathan\Documents\git-rag-chat\git-rag-chat"
codex
```

In chat:
```
List all available tools
```

Should show 22 tools from `chromadb_context_vespo`.

---

## ⚠️ Common Mistakes to Avoid

### ❌ Running Codex from Git Bash
```bash
# DON'T DO THIS:
$ codex
```

### ✅ Running Codex from PowerShell
```powershell
# DO THIS:
PS> codex
```

### ❌ Using Old Config Format
```toml
"-v","/c/Users/...://workspace:ro",  # Git Bash format - BAD
"-w","/workspace",                    # Causes failures - BAD
```

### ✅ Using New Config Format
```toml
"-v","C:\\Users\\...:/workspace:ro",  # PowerShell format - GOOD
# No -w flag                          # Fixed - GOOD
```

---

## 🔄 What If I Already Ran the Old Script?

No problem! This script will:

1. ✅ Backup your existing config
2. ✅ Remove the old `chromadb_context_vespo` section
3. ✅ Add the new fixed version
4. ✅ Preserve all other settings (model, echo server, etc.)

Just run it again:
```powershell
.\setup-codex-vespo-final.ps1
```

---

## 📊 Success Metrics

You'll know it worked when:

1. ✅ Script completes with green "SETUP SUCCESSFUL ✓" message
2. ✅ Config file has `C:\\Users\\...` format (not `/c/...`)
3. ✅ Config has NO `-w` flag
4. ✅ `codex mcp list` shows `chromadb_context_vespo`
5. ✅ Codex (from PowerShell) shows "List all available tools" works
6. ✅ No "connection closed" or "handshake failed" errors

---

## 📚 Related Documentation

- **Quick Start:** [QUICK_START.md](../../QUICK_START.md)
- **Troubleshooting:** [CODEX_TROUBLESHOOTING.md](../../CODEX_TROUBLESHOOTING.md)
- **Technical Details:** [PATCHING_SUMMARY.md](../../PATCHING_SUMMARY.md)
- **Script Improvements:** [SCRIPT_IMPROVEMENTS.md](SCRIPT_IMPROVEMENTS.md)
- **Full README:** [README.md](README.md)

---

## 🎉 Bottom Line

This is the **production-ready, fully tested, all-issues-fixed version**.

**Just run it and it will work.** 🚀

---

## Version History

- **v1.0** - Initial version with basic setup
- **v1.5** - Added GitHub clone and port selection
- **v2.0 (FINAL)** - Fixed PowerShell paths, removed -w flag, comprehensive validation

**Current: v2.0 - Final and Complete**

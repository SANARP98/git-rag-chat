# setup_mcp_echo.ps1
# Build a spec-correct MCP stdio "echo/ping" server in Docker and register it in Codex.

$ErrorActionPreference = "Stop"

Write-Host "==> [0/6] Preconditions" -ForegroundColor Cyan
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw "docker not found in PATH. Install Docker Desktop." }
if (-not (Get-Command codex -ErrorAction SilentlyContinue)) { throw "codex CLI not found in PATH." }

$WorkDir = "C:\mcp-echo"
$Image   = "mcp-echo"

Write-Host "==> [1/6] Create workdir: $WorkDir" -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $WorkDir | Out-Null

Write-Host "==> [2/6] Write spec-correct server.py + Dockerfile" -ForegroundColor Cyan

@'
import sys
import json

def eprint(*a):
    print(*a, file=sys.stderr, flush=True)

def send(obj):
    # IMPORTANT: MCP messages must be on stdout as JSON lines
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()

def read_json_line():
    """Read next non-empty JSON line. Skip blanks. Log parse errors to stderr only."""
    while True:
        line = sys.stdin.readline()
        if line == "":
            sys.exit(0)  # EOF
        line = line.strip()
        if not line:
            continue
        try:
            return json.loads(line)
        except json.JSONDecodeError as ex:
            eprint(f"[mcp-echo] Ignoring non-JSON line: {line!r} ({ex})")
            continue

# ---- 1) initialize ----
msg = read_json_line()
if msg.get("method") != "initialize":
    eprint("[mcp-echo] First message was not initialize; exiting.")
    sys.exit(1)

req_id = msg.get("id")
params = msg.get("params") or {}
client_proto = params.get("protocolVersion") or "2025-06-18"  # fallback

# Spec-correct capabilities: "tools" is an object, not a boolean
send({
    "jsonrpc": "2.0",
    "id": req_id,
    "result": {
        "protocolVersion": client_proto,
        "capabilities": {
            "tools": { "listChanged": False }
        },
        "serverInfo": {
            "name": "mcp-echo",
            "version": "1.1.0"
        }
    }
})

# ---- 2) wait for notifications/initialized (per lifecycle) ----
while True:
    m = read_json_line()
    if m.get("method") == "notifications/initialized":
        break
    # allow ping prior to initialized; ignore everything else
    if m.get("method") == "ping" and "id" in m:
        send({"jsonrpc":"2.0","id":m["id"],"result":{}})

# ---- 3) main loop ----
while True:
    msg = read_json_line()
    method = msg.get("method")
    mid = msg.get("id")

    if method == "ping" and mid is not None:
        send({"jsonrpc":"2.0","id":mid,"result":{}})

    elif method == "tools/list":
        send({
            "jsonrpc": "2.0",
            "id": mid,
            "result": {
                "tools": [
                    {
                        "name": "ping",
                        "description": "Returns pong",
                        "inputSchema": {"type": "object", "properties": {}}
                    }
                ]
            }
        })

    elif method == "tools/call":
        # Spec-ish: accept either params.name or params.toolName depending on client
        p = msg.get("params") or {}
        name = p.get("name") or p.get("toolName")
        if name != "ping":
            send({"jsonrpc":"2.0","id":mid,"error":{"code":-32602,"message":"Unknown tool"}})
            continue

        send({
            "jsonrpc": "2.0",
            "id": mid,
            "result": {
                "content": [
                    {"type": "text", "text": "pong"}
                ]
            }
        })

    else:
        # Unknown method
        if mid is not None:
            send({"jsonrpc":"2.0","id":mid,"error":{"code":-32601,"message":f"Method not found: {method}"}})
'@ | Set-Content -Path (Join-Path $WorkDir "server.py") -Encoding UTF8

@'
FROM python:3.11-slim
WORKDIR /app
COPY server.py .
CMD ["python", "server.py"]
'@ | Set-Content -Path (Join-Path $WorkDir "Dockerfile") -Encoding UTF8

Write-Host "==> [3/6] Build docker image: $Image" -ForegroundColor Cyan
Push-Location $WorkDir
docker build -t $Image . | Out-Host
Pop-Location

Write-Host "==> [4/6] Update Codex config: ~/.codex/config.toml" -ForegroundColor Cyan
$CodexDir = Join-Path $env:USERPROFILE ".codex"
$CodexCfg = Join-Path $CodexDir "config.toml"
if (-not (Test-Path $CodexDir)) { New-Item -ItemType Directory -Path $CodexDir | Out-Null }
if (-not (Test-Path $CodexCfg)) { New-Item -ItemType File -Path $CodexCfg | Out-Null }

$cfgText = Get-Content $CodexCfg -Raw
$cfgText = [regex]::Replace($cfgText, "(?ms)^\[mcp_servers\.echo\].*?(?=^\[|\z)", "").TrimEnd()

$block = @"
[mcp_servers.echo]
command = "docker"
args = ["run","--rm","-i","$Image"]
startup_timeout_sec = 20
tool_timeout_sec = 60
enabled = true

"@

Set-Content -Path $CodexCfg -Value ($cfgText + "`r`n`r`n" + $block) -Encoding UTF8
Write-Host "✅ Codex config updated: $CodexCfg" -ForegroundColor Green

Write-Host "==> [5/6] Manual test (copy/paste these into the running container)" -ForegroundColor Cyan
Write-Host "1) Run:" -ForegroundColor Yellow
Write-Host "   docker run --rm -i $Image" -ForegroundColor Yellow
Write-Host "2) Paste these lines, pressing Enter after each:" -ForegroundColor Yellow
Write-Host '   {"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"manual","version":"0"}}}' -ForegroundColor Yellow
Write-Host '   {"jsonrpc":"2.0","method":"notifications/initialized"}' -ForegroundColor Yellow
Write-Host '   {"jsonrpc":"2.0","id":2,"method":"tools/list"}' -ForegroundColor Yellow
Write-Host '   {"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"ping","arguments":{}}}' -ForegroundColor Yellow

Write-Host "==> [6/6] Verify Codex sees MCP servers" -ForegroundColor Cyan
codex mcp list | Out-Host

Write-Host ""
Write-Host "NEXT:" -ForegroundColor Green
Write-Host "1) Close Codex CLI + close VS Code completely." -ForegroundColor Green
Write-Host "2) Reopen VS Code and start a NEW Codex chat." -ForegroundColor Green
Write-Host "3) If 'echo' starts, we’ll apply the same sanity checks to chromadb_context." -ForegroundColor Green

#!/bin/bash
# Test script to simulate Codex CLI MCP handshake

echo "=== Testing MCP Server Handshake ==="
echo ""

# Start the server in background
echo "Starting MCP server..."
docker run --rm -i \
  --network chroma-net \
  -e CHROMA_URL=http://chromadb-vespo:8000 \
  -e CHROMADB_URL=http://chromadb-vespo:8000 \
  -v "/c/Users/prenganathan/OneDrive - Adaptive Biotechnologies/Documents/git-rag-chat/git-rag-chat://workspace:ro" \
  chroma-mcp-vespo-patched:latest &

SERVER_PID=$!
echo "Server PID: $SERVER_PID"

# Give it a moment to start
sleep 2

# Send initialize request
echo ""
echo "Sending initialize request..."
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"codex","version":"0.79.0"}}}' > /tmp/mcp_init.json

# Send via stdin
cat /tmp/mcp_init.json | nc -w 5 localhost 8003

echo ""
echo "Waiting for response..."
sleep 2

# Kill the server
kill $SERVER_PID 2>/dev/null

echo "Done"

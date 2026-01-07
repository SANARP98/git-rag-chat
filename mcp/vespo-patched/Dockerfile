# Dockerfile for MCP-compliant Chroma server (stdio clean)
# CRITICAL: This Dockerfile ensures ZERO stdout contamination during MCP handshake

FROM oven/bun:1

WORKDIR /app

# Copy all source files
COPY package.json bun.lock* ./
COPY *.js ./

# Install dependencies
# Using --silent to minimize potential stdout noise
RUN bun install --silent 2>&1 || bun install

# CRITICAL: Use direct bun execution (NOT "bun run")
# "bun run" can inject version banners or other output to stdout
# which breaks MCP stdio handshake
CMD ["bun", "index.js"]

# Health check (optional, won't affect stdio)
HEALTHCHECK NONE

#!/bin/bash
# Wrapper for the single-source setup script.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SETUP_SCRIPT="${SCRIPT_DIR}/setup-codex-vespo.js"

if ! command -v node >/dev/null 2>&1; then
  echo "ERROR: node is required to run ${SETUP_SCRIPT}" >&2
  exit 1
fi

exec node "${SETUP_SCRIPT}"

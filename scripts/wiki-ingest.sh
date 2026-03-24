#!/usr/bin/env bash
# Download, filter, and ingest Wikipedia into the knowledgebase.
#
# This is a long-running process (~22GB download + hours of processing).
# Each step is resumable — safe to interrupt and restart.
#
# Usage:
#   ./scripts/wiki-ingest.sh              # full run
#   ./scripts/wiki-ingest.sh --limit 100  # test with 100 articles
set -euo pipefail

NOMAD_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$NOMAD_DIR"
source .venv/bin/activate

echo "=== Stacks Wikipedia Ingest ==="
echo

# Step 1: Download
echo "--- Step 1: Download dump ---"
stacks wiki download
echo

# Step 2: Build category hierarchy
echo "--- Step 2: Build category graph ---"
stacks wiki build-categories
echo

# Step 3: Ingest (filtered)
echo "--- Step 3: Ingest filtered articles ---"
stacks wiki ingest-wiki "$@"
echo

echo "=== Done ==="
stacks wiki status

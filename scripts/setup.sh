#!/usr/bin/env bash
# First-time setup for Stacks knowledgebase.
set -euo pipefail

NOMAD_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$NOMAD_DIR"

echo "=== Stacks Setup ==="
echo "Directory: $NOMAD_DIR"
echo

# Python venv
if [ ! -d .venv ]; then
    echo "Creating Python venv..."
    python3 -m venv .venv
else
    echo "Venv already exists."
fi

echo "Installing dependencies..."
source .venv/bin/activate
pip install -q -e .

# Ollama
if ! command -v ollama &>/dev/null; then
    echo
    echo "ERROR: ollama is not installed."
    echo "Install it from https://ollama.com and re-run this script."
    exit 1
fi

# Check if ollama is running
if ! curl -sf http://localhost:11434/api/tags &>/dev/null; then
    echo
    echo "Ollama is not running. Starting it..."
    if [ -n "${OLLAMA_MODELS:-}" ]; then
        echo "Using OLLAMA_MODELS=$OLLAMA_MODELS"
    fi
    echo "Run: ./scripts/ollama-start.sh"
    echo "Then re-run this script to pull the embedding model."
    exit 0
fi

# Pull embedding model if missing
if ! ollama list 2>/dev/null | grep -q "nomic-embed-text"; then
    echo "Pulling embedding model (nomic-embed-text:v1.5)..."
    ollama pull nomic-embed-text:v1.5
else
    echo "Embedding model already available."
fi

echo
echo "=== Setup complete ==="
echo
echo "Quick start:"
echo "  source .venv/bin/activate"
echo "  stacks ingest /path/to/ebooks -r"
echo "  stacks search \"your query\""
echo "  stacks ask"

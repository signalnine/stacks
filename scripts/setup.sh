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

source .venv/bin/activate

# Install with CUDA support for llama-cpp-python
echo "Installing dependencies (with CUDA support)..."
CMAKE_ARGS="-DGGML_CUDA=on" pip install -q -e .

# Check for embedding model
EMBED_MODEL="/mnt/ai/models/nomic-embed-text-v1.5.Q8_0.gguf"
if [ ! -f "$EMBED_MODEL" ]; then
    echo
    echo "Embedding model not found at $EMBED_MODEL"
    echo "Download it:"
    echo "  huggingface-cli download nomic-ai/nomic-embed-text-v1.5-GGUF nomic-embed-text-v1.5.Q8_0.gguf --local-dir /mnt/ai/models/"
fi

echo
echo "=== Setup complete ==="
echo
echo "Quick start:"
echo "  source .venv/bin/activate"
echo "  stacks ingest /path/to/ebooks -r"
echo "  stacks search \"your query\""
echo "  stacks ask"

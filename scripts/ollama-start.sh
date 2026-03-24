#!/usr/bin/env bash
# Start ollama with the correct model directory.
# Keeps running in the foreground — run in a tmux pane or background it.
set -euo pipefail

export OLLAMA_MODELS="${OLLAMA_MODELS:-/mnt/ai/models/ollama}"

echo "Starting ollama..."
echo "  OLLAMA_MODELS=$OLLAMA_MODELS"
echo "  Host: http://localhost:11434"
echo

exec ollama serve

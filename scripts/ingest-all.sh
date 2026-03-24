#!/usr/bin/env bash
# Batch ingest the entire ebook library.
# Run this in the background — it'll take a while for large collections.
#
# Usage:
#   ./scripts/ingest-all.sh                    # default: /mnt/soma/backup/ebooks
#   ./scripts/ingest-all.sh /other/ebooks/dir
set -euo pipefail

NOMAD_DIR="$(cd "$(dirname "$0")/.." && pwd)"
EBOOKS_DIR="${1:-/mnt/soma/backup/ebooks}"
LOG="$NOMAD_DIR/data/ingest.log"

cd "$NOMAD_DIR"
source .venv/bin/activate
mkdir -p data

echo "=== Stacks Batch Ingest ==="
echo "Source: $EBOOKS_DIR"
echo "Log:    $LOG"
echo

echo "Starting ingest at $(date)..." | tee "$LOG"
echo | tee -a "$LOG"

# Ingest each top-level item separately so failures don't kill the whole run
for item in "$EBOOKS_DIR"/*; do
    echo "--- $(basename "$item") ---" | tee -a "$LOG"
    if [ -f "$item" ]; then
        stacks ingest "$item" 2>&1 | tee -a "$LOG"
    elif [ -d "$item" ]; then
        stacks ingest "$item" -r 2>&1 | tee -a "$LOG"
    fi
    echo | tee -a "$LOG"
done

echo "=== Ingest complete at $(date) ===" | tee -a "$LOG"
stacks stats

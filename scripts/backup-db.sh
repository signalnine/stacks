#!/usr/bin/env bash
# Back up the ChromaDB vector database.
# Creates a timestamped tarball in ~/nomad/backups/.
set -euo pipefail

NOMAD_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_DIR="$NOMAD_DIR/backups"
DB_DIR="$NOMAD_DIR/data/chromadb"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_FILE="$BACKUP_DIR/chromadb-$TIMESTAMP.tar.zst"

if [ ! -d "$DB_DIR" ]; then
    echo "No database found at $DB_DIR"
    exit 1
fi

mkdir -p "$BACKUP_DIR"

DB_SIZE="$(du -sh "$DB_DIR" | cut -f1)"
echo "Backing up ChromaDB ($DB_SIZE)..."

tar -C "$NOMAD_DIR/data" -cf - chromadb | zstd -3 -o "$BACKUP_FILE"

BACKUP_SIZE="$(du -sh "$BACKUP_FILE" | cut -f1)"
echo "Backup: $BACKUP_FILE ($BACKUP_SIZE)"

# Keep only last 5 backups
cd "$BACKUP_DIR"
ls -t chromadb-*.tar.zst 2>/dev/null | tail -n +6 | xargs -r rm --
KEPT=$(ls chromadb-*.tar.zst 2>/dev/null | wc -l)
echo "Retained $KEPT backup(s)."

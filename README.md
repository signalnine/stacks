# Stacks

Local knowledgebase with semantic search and RAG chat, powered by Ollama and ChromaDB. No Docker, no cloud, no nonsense.

Ingest your ebooks (epub, pdf, mobi, txt), search them semantically, and chat with an LLM that uses your library as context. Also includes an offline maps viewer.

## Requirements

- Python 3.12+
- [Ollama](https://ollama.com) installed locally
- GPU recommended (embeddings are fast on even modest hardware)

## Setup

```bash
cd ~/nomad
./scripts/setup.sh
```

This creates a venv, installs dependencies, and pulls the embedding model.

If you keep Ollama models somewhere other than the default, set the env var:

```bash
export OLLAMA_MODELS=/mnt/ai/models/ollama
```

Or make it permanent with the systemd override (see `scripts/setup.sh`).

## Usage

Activate the venv first, or use the wrapper scripts in `scripts/`.

```bash
source .venv/bin/activate
```

### Ingest

Add documents to the knowledgebase. Supports `.epub`, `.pdf`, `.mobi`, `.txt`, `.md`.

```bash
# Single file
stacks ingest /path/to/book.epub

# Entire directory (recursive)
stacks ingest /mnt/soma/backup/ebooks -r

# Multiple paths
stacks ingest book1.pdf book2.epub /path/to/more/books -r
```

Already-ingested files are skipped automatically.

### Search

Semantic search across everything you've ingested.

```bash
stacks search "how to purify water"
stacks search "predictive processing and bayesian inference" -k 10
```

### Chat

Interactive RAG chat. Searches the knowledgebase for context, feeds it to the LLM.

```bash
# Default model (qwen3)
stacks ask

# Pick a model
stacks ask -m mixtral8x7b:latest

# More context chunks
stacks ask -k 10
```

Type `quit` or Ctrl+C to exit.

### Stats & Management

```bash
# What's in the knowledgebase
stacks stats

# Remove a source
stacks remove /path/to/book.epub
```

### Offline Maps

Serves a local MapLibre GL viewer for PMTiles files.

```bash
# Just launch the viewer
stacks maps

# Point it at a directory of .pmtiles files
stacks maps -t /path/to/tiles/

# Custom port, no auto-open
stacks maps -p 9000 --no-browser
```

You'll need PMTiles files — download regional or global extracts from
[protomaps.com/builds](https://maps.protomaps.com/builds/).

### Wikipedia

Download and ingest a filtered copy of English Wikipedia — pop culture
articles (film, TV, video games, celebrities, anime, etc.) are excluded
via category tree crawling.

```bash
# One-shot: download, build category graph, and ingest
./scripts/wiki-ingest.sh

# Or step by step:
stacks wiki download                  # ~22GB, resumable
stacks wiki build-categories          # builds category hierarchy (~20-30 min)
stacks wiki show-exclusions           # see what's being filtered out
stacks wiki ingest-wiki               # filter + embed articles (hours, resumable)
stacks wiki ingest-wiki --limit 100   # test with a small batch first
stacks wiki status                    # check progress
```

The exclusion list covers ~60 root categories (Films, Television, Video games,
Anime, Celebrities, etc.) and all their subcategories. To customize, edit
`EXCLUDE_ROOTS` in `src/stacks/wiki.py`.

Every step is resumable — safe to Ctrl+C and restart.

## Project Structure

```
~/nomad/
├── src/stacks/
│   ├── cli.py          # Click CLI commands
│   ├── config.py       # All tunable settings
│   ├── extract.py      # Text extraction (epub/pdf/mobi/txt)
│   ├── chunker.py      # Text chunking for embedding
│   ├── store.py        # ChromaDB + Ollama embedding interface
│   ├── rag.py          # RAG chat logic
│   ├── wiki.py         # Wikipedia dump download, filter, and ingest
│   └── maps_server.py  # Local maps HTTP server
├── maps/
│   └── index.html      # MapLibre GL + PMTiles viewer
├── data/
│   ├── chromadb/       # Vector database (created on first ingest)
│   └── wiki/           # Wikipedia dump + category cache + progress
├── scripts/
│   ├── setup.sh        # First-time setup
│   ├── ingest-all.sh   # Batch ingest the ebook library
│   ├── wiki-ingest.sh  # Download + filter + ingest Wikipedia
│   ├── ollama-start.sh # Start ollama with the right env
│   └── backup-db.sh    # Back up the vector database
└── pyproject.toml
```

## Configuration

Edit `src/stacks/config.py` to change defaults:

| Setting | Default | Description |
|---|---|---|
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama API endpoint |
| `EMBED_MODEL` | `nomic-embed-text:v1.5` | Model for embeddings (768d) |
| `CHAT_MODEL` | `qwen3:latest` | Default chat model |
| `CHUNK_SIZE` | `4000` | Characters per chunk (~1300 tokens) |
| `CHUNK_OVERLAP` | `400` | Overlap between chunks |
| `DEFAULT_TOP_K` | `5` | Number of search results |
| `SIMILARITY_THRESHOLD` | `0.25` | Minimum cosine similarity to include |
| `EBOOKS_DIR` | `/mnt/soma/backup/ebooks` | Default ebook library path |

## How It Works

1. **Ingest**: Extract text from documents → split into overlapping chunks → embed with `nomic-embed-text` via Ollama → store vectors + text in ChromaDB
2. **Search**: Embed your query → cosine similarity search against stored vectors → return ranked results
3. **Chat**: Search for relevant chunks → inject as context into a system prompt → stream LLM response via Ollama

# Stacks

Local knowledgebase with semantic search and RAG chat, powered by llama.cpp and ChromaDB. No Docker, no cloud, no nonsense.

Ingest your ebooks (epub, pdf, mobi, txt), search them semantically, and chat with an LLM that uses your library as context. Also includes an offline maps viewer.

## Requirements

- Python 3.12+
- NVIDIA GPU with CUDA (for llama-cpp-python GPU acceleration)
- GGUF model files for embedding and chat

## Setup

```bash
cd ~/nomad
./scripts/setup.sh
```

This creates a venv, installs dependencies with CUDA support, and checks for the embedding model.

You'll need the nomic-embed-text GGUF for embeddings:

```bash
huggingface-cli download nomic-ai/nomic-embed-text-v1.5-GGUF \
    nomic-embed-text-v1.5.Q8_0.gguf --local-dir /mnt/ai/models/
```

And any GGUF chat model you like (e.g. Qwen, Mixtral, etc.) in your models directory.

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
# Default model
stacks ask

# Pick a specific GGUF model
stacks ask -m /mnt/ai/models/mixtral-8x7b.gguf

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
│   ├── store.py        # ChromaDB + llama-cpp-python embedding interface
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
│   └── backup-db.sh    # Back up the vector database
└── pyproject.toml
```

## Configuration

Edit `src/stacks/config.py` to change defaults:

| Setting | Default | Description |
|---|---|---|
| `MODELS_DIR` | `/mnt/ai/models` | Directory containing GGUF files |
| `EMBED_MODEL` | `nomic-embed-text-v1.5.Q8_0.gguf` | Embedding model (768d) |
| `CHAT_MODEL` | `qwen3-coder-30b-a3b.gguf` | Default chat model |
| `N_GPU_LAYERS` | `-1` | GPU layers to offload (-1 = all) |
| `CHUNK_SIZE` | `4000` | Characters per chunk (~1300 tokens) |
| `CHUNK_OVERLAP` | `400` | Overlap between chunks |
| `DEFAULT_TOP_K` | `5` | Number of search results |
| `SIMILARITY_THRESHOLD` | `0.25` | Minimum cosine similarity to include |
| `EBOOKS_DIR` | `/mnt/soma/backup/ebooks` | Default ebook library path |

## How It Works

1. **Ingest**: Extract text from documents → split into overlapping chunks → embed with `nomic-embed-text` via llama-cpp-python → store vectors + text in ChromaDB
2. **Search**: Embed your query → cosine similarity search against stored vectors → return ranked results
3. **Chat**: Search for relevant chunks → inject as context into a system prompt → stream LLM response via llama-cpp-python

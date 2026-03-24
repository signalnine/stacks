"""Configuration for stacks knowledgebase."""

from pathlib import Path

# Ollama
OLLAMA_HOST = "http://localhost:11434"
EMBED_MODEL = "nomic-embed-text:v1.5"
CHAT_MODEL = "qwen3:latest"  # override via --model flag

# ChromaDB
DATA_DIR = Path.home() / "stacks" / "data"
CHROMA_DIR = DATA_DIR / "chromadb"
COLLECTION_NAME = "knowledgebase"

# Chunking
CHUNK_SIZE = 4000  # chars (~1300 tokens)
CHUNK_OVERLAP = 400  # chars

# Search
DEFAULT_TOP_K = 5
SIMILARITY_THRESHOLD = 0.25

# Ebooks
EBOOKS_DIR = Path("/mnt/soma/backup/ebooks")

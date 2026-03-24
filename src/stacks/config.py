"""Configuration for stacks knowledgebase."""

from pathlib import Path

# Models (paths to GGUF files)
MODELS_DIR = Path("/mnt/ai/models")
EMBED_MODEL = MODELS_DIR / "nomic-embed-text-v1.5.Q8_0.gguf"
CHAT_MODEL = MODELS_DIR / "qwen3-coder-30b-a3b.gguf"  # override via --model flag

# GPU
N_GPU_LAYERS = -1  # -1 = offload all layers

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

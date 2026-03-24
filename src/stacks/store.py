"""ChromaDB vector store interface."""

import chromadb
from llama_cpp import Llama
from llama_cpp._internals import LlamaContext

from stacks.config import CHROMA_DIR, COLLECTION_NAME, EMBED_MODEL, N_GPU_LAYERS

# Patch: BERT-style embedding models have no KV cache, but llama-cpp-python
# tries to clear it. Skip the clear when memory isn't initialized.
_orig_kv_clear = LlamaContext.kv_cache_clear
LlamaContext.kv_cache_clear = lambda self: _orig_kv_clear(self) if self.memory is not None else None

MAX_EMBED_CHARS = 7500  # ~2500 tokens, safe limit for nomic-embed-text (2048 token context)

_embed_model: Llama | None = None


def _get_embed_model() -> Llama:
    global _embed_model
    if _embed_model is None:
        _embed_model = Llama(
            model_path=str(EMBED_MODEL),
            n_gpu_layers=N_GPU_LAYERS,
            embedding=True,
            n_ctx=2048,
            verbose=False,
        )
    return _embed_model


def get_client() -> chromadb.PersistentClient:
    """Get or create ChromaDB persistent client."""
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(CHROMA_DIR))


def get_collection(client: chromadb.PersistentClient) -> chromadb.Collection:
    """Get or create the knowledgebase collection."""
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Generate embeddings via llama-cpp-python."""
    model = _get_embed_model()
    embeddings = []
    for text in texts:
        truncated = text[:MAX_EMBED_CHARS]
        vec = model.embed(f"search_document: {truncated}")
        embeddings.append(vec)
    return embeddings


def embed_query(text: str) -> list[float]:
    """Generate a query embedding via llama-cpp-python."""
    model = _get_embed_model()
    return model.embed(f"search_query: {text}")


def add_chunks(
    collection: chromadb.Collection,
    chunks: list[str],
    metadata: dict,
    source_path: str,
    batch_size: int = 32,
):
    """Embed and store text chunks with metadata."""
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        embeddings = embed_texts(batch)
        ids = [f"{source_path}::{i + j}" for j in range(len(batch))]
        metadatas = [
            {**metadata, "source": source_path, "chunk_index": i + j}
            for j in range(len(batch))
        ]
        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=batch,
            metadatas=metadatas,
        )


def search(collection: chromadb.Collection, query: str, top_k: int = 5) -> dict:
    """Search the collection with a query string."""
    query_embedding = embed_query(query)
    return collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )


def list_sources(collection: chromadb.Collection) -> list[dict]:
    """List all unique sources in the collection."""
    seen = {}
    offset = 0
    page_size = 5000

    while True:
        results = collection.get(include=["metadatas"], limit=page_size, offset=offset)
        if not results["metadatas"]:
            break
        for meta in results["metadatas"]:
            src = meta.get("source", "unknown")
            if src not in seen:
                seen[src] = {
                    "source": src,
                    "title": meta.get("title", "Unknown"),
                    "author": meta.get("author", "Unknown"),
                    "format": meta.get("format", "unknown"),
                }
        if len(results["metadatas"]) < page_size:
            break
        offset += page_size

    return list(seen.values())


def get_stats(collection: chromadb.Collection) -> dict:
    """Get collection statistics."""
    count = collection.count()
    sources = list_sources(collection)
    return {"total_chunks": count, "total_sources": len(sources), "sources": sources}

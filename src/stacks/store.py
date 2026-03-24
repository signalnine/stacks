"""ChromaDB vector store interface."""

import chromadb
import ollama as ollama_client

from stacks.config import CHROMA_DIR, COLLECTION_NAME, EMBED_MODEL, OLLAMA_HOST


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


MAX_EMBED_CHARS = 7500  # ~2500 tokens, safe limit for nomic-embed-text (2048 token context)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Generate embeddings via Ollama."""
    client = ollama_client.Client(host=OLLAMA_HOST)
    # Truncate to stay within model context length
    truncated = [t[:MAX_EMBED_CHARS] for t in texts]
    # Prefix for nomic-embed-text
    prefixed = [f"search_document: {t}" for t in truncated]
    resp = client.embed(model=EMBED_MODEL, input=prefixed)
    return resp.embeddings


def embed_query(text: str) -> list[float]:
    """Generate a query embedding via Ollama."""
    client = ollama_client.Client(host=OLLAMA_HOST)
    resp = client.embed(model=EMBED_MODEL, input=[f"search_query: {text}"])
    return resp.embeddings[0]


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

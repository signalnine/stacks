"""RAG chat - query the knowledgebase and chat with context."""

from llama_cpp import Llama

from stacks.config import CHAT_MODEL, N_GPU_LAYERS, DEFAULT_TOP_K, SIMILARITY_THRESHOLD
from stacks.store import get_client, get_collection, search


SYSTEM_PROMPT = """You are a knowledgeable assistant with access to a personal library. \
Use the provided context from the knowledgebase to answer questions accurately. \
If the context doesn't contain relevant information, say so and answer from your general knowledge. \
Cite the source document when using information from the context."""

RAG_CONTEXT_TEMPLATE = """Relevant context from the knowledgebase:

{context}

---
Answer the user's question using the above context when relevant."""


_chat_model: Llama | None = None
_chat_model_path: str | None = None


def _get_chat_model(model_path: str) -> Llama:
    global _chat_model, _chat_model_path
    if _chat_model is None or _chat_model_path != model_path:
        del _chat_model
        _chat_model = Llama(
            model_path=model_path,
            n_gpu_layers=N_GPU_LAYERS,
            n_ctx=8192,
            verbose=False,
        )
        _chat_model_path = model_path
    return _chat_model


def format_context(results: dict) -> str:
    """Format search results as context for the LLM."""
    if not results["documents"] or not results["documents"][0]:
        return ""

    sections = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        # ChromaDB cosine distance: 0 = identical, 2 = opposite
        similarity = 1 - dist
        if similarity < SIMILARITY_THRESHOLD:
            continue
        source = meta.get("title", meta.get("source", "Unknown"))
        author = meta.get("author", "")
        header = f"[{source}"
        if author and author != "Unknown":
            header += f" by {author}"
        header += f"] (relevance: {similarity:.0%})"
        sections.append(f"{header}\n{doc}")

    return "\n\n---\n\n".join(sections)


def chat(
    query: str,
    model: str,
    top_k: int = DEFAULT_TOP_K,
    history: list[dict] | None = None,
    stream: bool = True,
):
    """RAG chat: search knowledgebase, inject context, stream response."""
    client = get_client()
    collection = get_collection(client)

    # Search for relevant context
    results = search(collection, query, top_k=top_k)
    context = format_context(results)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if history:
        messages.extend(history)

    if context:
        user_msg = f"{RAG_CONTEXT_TEMPLATE.format(context=context)}\n\nQuestion: {query}"
    else:
        user_msg = query

    messages.append({"role": "user", "content": user_msg})

    llm = _get_chat_model(model)
    return llm.create_chat_completion(messages=messages, stream=stream)

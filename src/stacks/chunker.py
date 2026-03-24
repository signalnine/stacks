"""Text chunking for embedding."""

from stacks.config import CHUNK_SIZE, CHUNK_OVERLAP


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks, breaking at paragraph/sentence boundaries."""
    if not text.strip():
        return []

    # Normalize whitespace but preserve paragraph breaks
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 > chunk_size and current:
            chunks.append(current.strip())
            # Keep overlap from end of current chunk
            if overlap > 0:
                current = current[-overlap:] + "\n\n" + para
            else:
                current = para
        else:
            current = current + "\n\n" + para if current else para

    if current.strip():
        chunks.append(current.strip())

    # Handle single paragraphs that exceed chunk_size
    final = []
    for chunk in chunks:
        if len(chunk) <= chunk_size:
            final.append(chunk)
        else:
            # Force-split long chunks at sentence boundaries
            sentences = chunk.replace(". ", ".\n").split("\n")
            sub = ""
            for sent in sentences:
                if len(sub) + len(sent) + 1 > chunk_size and sub:
                    final.append(sub.strip())
                    sub = sub[-overlap:] + " " + sent if overlap else sent
                else:
                    sub = sub + " " + sent if sub else sent
            if sub.strip():
                final.append(sub.strip())

    return final

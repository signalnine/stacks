"""Text extraction from various ebook formats."""

import html2text
from pathlib import Path


h2t = html2text.HTML2Text()
h2t.ignore_links = True
h2t.ignore_images = True
h2t.ignore_emphasis = False
h2t.body_width = 0


def extract_epub(path: Path) -> tuple[str, dict]:
    """Extract text from EPUB files."""
    import ebooklib
    from ebooklib import epub

    book = epub.read_epub(str(path), options={"ignore_ncx": True})
    title = book.get_metadata("DC", "title")
    title = title[0][0] if title else path.stem
    author = book.get_metadata("DC", "creator")
    author = author[0][0] if author else "Unknown"

    chunks = []
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        content = item.get_content().decode("utf-8", errors="replace")
        text = h2t.handle(content).strip()
        if text:
            chunks.append(text)

    return "\n\n".join(chunks), {"title": title, "author": author, "format": "epub"}


def extract_pdf(path: Path) -> tuple[str, dict]:
    """Extract text from PDF files."""
    import pymupdf

    doc = pymupdf.open(str(path))
    title = doc.metadata.get("title", "") or path.stem
    author = doc.metadata.get("author", "") or "Unknown"

    chunks = []
    for page in doc:
        text = page.get_text().strip()
        if text:
            chunks.append(text)

    doc.close()
    return "\n\n".join(chunks), {"title": title, "author": author, "format": "pdf"}


def extract_mobi(path: Path) -> tuple[str, dict]:
    """Extract text from MOBI files."""
    import mobi

    tempdir, filepath = mobi.extract(str(path))
    # mobi.extract returns the path to an HTML file
    content = Path(filepath).read_text(errors="replace")
    text = h2t.handle(content).strip()

    return text, {"title": path.stem, "author": "Unknown", "format": "mobi"}


def extract_txt(path: Path) -> tuple[str, dict]:
    """Extract text from plain text files."""
    text = path.read_text(errors="replace")
    return text, {"title": path.stem, "author": "Unknown", "format": "txt"}


EXTRACTORS = {
    ".epub": extract_epub,
    ".pdf": extract_pdf,
    ".mobi": extract_mobi,
    ".txt": extract_txt,
    ".md": extract_txt,
}


def extract(path: Path) -> tuple[str, dict]:
    """Extract text from a file based on its extension."""
    ext = path.suffix.lower()
    if ext not in EXTRACTORS:
        raise ValueError(f"Unsupported format: {ext}")
    return EXTRACTORS[ext](path)


def supported_extensions() -> set[str]:
    return set(EXTRACTORS.keys())

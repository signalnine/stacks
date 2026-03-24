"""Wikipedia dump download, category filtering, and ingest."""

import bz2
import json
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

import mwparserfromhell

from stacks.config import DATA_DIR

DUMP_DIR = DATA_DIR / "wiki"
CATEGORY_CACHE = DUMP_DIR / "category_graph.json"
PROGRESS_FILE = DUMP_DIR / "ingest_progress.json"

DUMP_BASE_URL = "https://dumps.wikimedia.org/enwiki/latest"
DUMP_FILENAME = "enwiki-latest-pages-articles.xml.bz2"

# Category namespace in MediaWiki
NS_ARTICLE = "0"
NS_CATEGORY = "14"

# Categories to exclude — top-level roots, subcategories are crawled automatically.
EXCLUDE_ROOTS = {
    # Film & TV
    "Films", "Television", "Television series", "Film genres",
    "Television genres", "Soap operas", "Reality television",
    "Animated television series", "Television films",
    # Music (popular)
    "Popular music", "Rock music", "Hip hop music", "Pop music",
    "Electronic dance music", "K-pop", "J-pop", "Music videos",
    "Record labels", "Musical groups", "Singers",
    "Albums", "Singles (music)", "Concerts", "Music festivals",
    # Gaming
    "Video games", "Esports", "Video game genres",
    "Video game companies", "Arcade games",
    # Celebrities & entertainment
    "Celebrities", "Internet celebrities", "YouTubers",
    "TikTok", "Influencers", "Streamers",
    "Beauty pageants", "Fashion models",
    # Comics, anime, manga
    "Anime", "Manga", "Comic books", "Comics",
    "Superhero fiction", "DC Comics", "Marvel Comics",
    "Webcomics",
    # Professional wrestling
    "Professional wrestling",
    # Fictional content
    "Fictional characters", "Fictional organizations",
    "Fictional locations", "Fictional technology",
    # Gossip / tabloid
    "Scandals", "Paparazzi", "Tabloid journalism",
    # Social media specifics
    "Internet memes", "Viral videos",
    # Reality / competition shows
    "Reality television series", "Talent shows",
    "Game shows",
    # Romance / fan culture
    "Fan fiction", "Fandom", "Shipping (fandom)",
    # Award shows (entertainment)
    "Film award ceremonies", "Music award ceremonies",
    "Television award ceremonies",
}

# Regex to extract [[Category:Name]] or [[Category:Name|sortkey]] from wikitext
CATEGORY_RE = re.compile(r"\[\[Category:([^\]|]+)(?:\|[^\]]*)?\]\]", re.IGNORECASE)


def get_dump_path() -> Path:
    """Path to the downloaded dump file."""
    return DUMP_DIR / DUMP_FILENAME


def download_dump(resume: bool = True):
    """Download the Wikipedia articles dump. Supports resume."""
    import urllib.request

    DUMP_DIR.mkdir(parents=True, exist_ok=True)
    dest = get_dump_path()
    url = f"{DUMP_BASE_URL}/{DUMP_FILENAME}"

    headers = {}
    mode = "ab"
    existing_size = 0

    if resume and dest.exists():
        existing_size = dest.stat().st_size
        headers["Range"] = f"bytes={existing_size}-"
        print(f"Resuming download from {existing_size / 1e9:.1f} GB...")
    else:
        mode = "wb"
        print(f"Downloading {url}...")

    req = urllib.request.Request(url, headers=headers)
    try:
        resp = urllib.request.urlopen(req)
    except urllib.error.HTTPError as e:
        if e.code == 416:
            print("Download already complete.")
            return dest
        raise

    total = resp.headers.get("Content-Length")
    if total:
        total = int(total) + existing_size
        print(f"Total size: {total / 1e9:.1f} GB")

    with open(dest, mode) as f:
        downloaded = existing_size
        while True:
            chunk = resp.read(1024 * 1024)  # 1MB chunks
            if not chunk:
                break
            f.write(chunk)
            downloaded += len(chunk)
            if total:
                pct = downloaded / total * 100
                print(f"\r  {downloaded / 1e9:.2f} / {total / 1e9:.2f} GB ({pct:.1f}%)", end="", flush=True)
            else:
                print(f"\r  {downloaded / 1e9:.2f} GB", end="", flush=True)

    print("\nDownload complete.")
    return dest


def iter_pages(dump_path: Path):
    """Stream-parse the XML dump, yielding (page_id, ns, title, text) tuples.

    Uses incremental parsing to handle the ~90GB uncompressed XML without
    loading it all into memory.
    """
    # The XML uses a namespace — detect it from the root element
    ns_uri = None

    with bz2.open(dump_path, "rb") as f:
        context = ET.iterparse(f, events=("start", "end"))

        page_id = None
        page_ns = None
        page_title = None
        page_text = None
        in_page = False
        in_revision = False

        for event, elem in context:
            tag = elem.tag

            # Strip namespace URI from tag
            if "}" in tag:
                if ns_uri is None:
                    ns_uri = tag.split("}")[0] + "}"
                tag = tag.split("}")[1]

            if event == "start":
                if tag == "page":
                    in_page = True
                    page_id = page_ns = page_title = page_text = None
                elif tag == "revision":
                    in_revision = True

            elif event == "end":
                if tag == "page":
                    if page_id and page_ns is not None and page_title:
                        yield page_id, page_ns, page_title, page_text or ""
                    in_page = False
                    # Free memory
                    elem.clear()
                elif tag == "revision":
                    in_revision = False
                elif in_page and not in_revision:
                    if tag == "id" and page_id is None:
                        page_id = elem.text
                    elif tag == "ns":
                        page_ns = elem.text
                    elif tag == "title":
                        page_title = elem.text
                elif in_revision and tag == "text":
                    page_text = elem.text


def extract_categories(wikitext: str) -> set[str]:
    """Extract category names from wikitext."""
    return {m.group(1).strip().replace(" ", "_") for m in CATEGORY_RE.finditer(wikitext)}


def build_category_graph(dump_path: Path, force: bool = False) -> dict[str, set[str]]:
    """Pass 1: Build a category -> set of parent categories graph.

    Only reads Category namespace pages. Caches result to disk.
    """
    if not force and CATEGORY_CACHE.exists():
        print(f"Loading cached category graph from {CATEGORY_CACHE}")
        data = json.loads(CATEGORY_CACHE.read_text())
        return {k: set(v) for k, v in data.items()}

    print("Pass 1: Building category hierarchy (this takes ~20-30 min)...")
    # child_category -> set of parent categories
    graph = defaultdict(set)
    count = 0

    for page_id, ns, title, text in iter_pages(dump_path):
        if ns != NS_CATEGORY:
            continue
        # Title is like "Category:Foo" — strip prefix
        cat_name = title.replace("Category:", "").replace(" ", "_")
        parents = extract_categories(text)
        graph[cat_name] = parents
        count += 1
        if count % 50000 == 0:
            print(f"  Processed {count:,} categories...")

    print(f"  Done: {count:,} categories total.")

    # Cache to disk
    DUMP_DIR.mkdir(parents=True, exist_ok=True)
    serializable = {k: list(v) for k, v in graph.items()}
    CATEGORY_CACHE.write_text(json.dumps(serializable))
    print(f"  Cached to {CATEGORY_CACHE}")

    return dict(graph)


def build_exclusion_set(graph: dict[str, set[str]], roots: set[str] | None = None) -> set[str]:
    """BFS from exclusion root categories through the graph to find all excluded categories.

    The graph maps child -> parents, so we need to invert it to parent -> children
    for top-down traversal.
    """
    if roots is None:
        roots = EXCLUDE_ROOTS

    # Normalize root names
    roots = {r.replace(" ", "_") for r in roots}

    # Invert: parent -> children
    children_of = defaultdict(set)
    for child, parents in graph.items():
        for parent in parents:
            children_of[parent].add(child)

    # BFS from roots
    excluded = set()
    queue = list(roots)

    while queue:
        cat = queue.pop()
        if cat in excluded:
            continue
        excluded.add(cat)
        for child in children_of.get(cat, set()):
            if child not in excluded:
                queue.append(child)

    print(f"Exclusion set: {len(excluded):,} categories (from {len(roots)} roots)")
    return excluded


def wikitext_to_plaintext(wikitext: str) -> str:
    """Convert wikitext to readable plain text."""
    try:
        parsed = mwparserfromhell.parse(wikitext)
        text = parsed.strip_code(normalize=True, collapse=True)
    except Exception:
        # Fallback: crude regex cleanup
        text = re.sub(r"\{\{[^}]*\}\}", "", wikitext)
        text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", text)
        text = re.sub(r"'{2,}", "", text)
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"==+\s*(.*?)\s*==+", r"\n\1\n", text)

    # Clean up whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def is_article_excluded(categories: set[str], exclusion_set: set[str]) -> bool:
    """Check if an article should be excluded based on its categories."""
    return bool(categories & exclusion_set)


def load_progress() -> dict:
    """Load ingest progress state."""
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text())
    return {"last_page_id": 0, "articles_ingested": 0, "articles_skipped": 0}


def save_progress(state: dict):
    """Save ingest progress state."""
    PROGRESS_FILE.write_text(json.dumps(state))


def ingest_wiki(
    dump_path: Path,
    exclusion_set: set[str],
    batch_size: int = 50,
    resume: bool = True,
    limit: int | None = None,
):
    """Pass 2: Stream articles, filter, and ingest into the knowledgebase.

    Processes articles in batches for efficiency. Resumable via progress file.
    """
    from stacks.chunker import chunk_text
    from stacks.store import get_client, get_collection, add_chunks

    client = get_client()
    collection = get_collection(client)

    progress = load_progress() if resume else {"last_page_id": 0, "articles_ingested": 0, "articles_skipped": 0}
    last_id = int(progress["last_page_id"])
    ingested = progress["articles_ingested"]
    skipped = progress["articles_skipped"]

    if last_id > 0:
        print(f"Resuming from page_id {last_id} ({ingested:,} ingested, {skipped:,} skipped)")

    print("Pass 2: Filtering and ingesting articles...")

    for page_id, ns, title, text in iter_pages(dump_path):
        if ns != NS_ARTICLE:
            continue

        pid = int(page_id)
        if pid <= last_id:
            continue

        # Skip redirects
        if text and text.strip().upper().startswith("#REDIRECT"):
            continue

        # Skip stubs and very short articles
        if not text or len(text) < 500:
            continue

        # Check categories
        categories = extract_categories(text)
        if is_article_excluded(categories, exclusion_set):
            skipped += 1
            if skipped % 10000 == 0:
                print(f"  Skipped {skipped:,} (excluded) | Ingested {ingested:,} | at page_id {page_id}")
            continue

        # Convert to plain text
        plaintext = wikitext_to_plaintext(text)
        if len(plaintext) < 200:
            continue

        # Chunk and embed
        chunks = chunk_text(plaintext)
        if chunks:
            source = f"wikipedia:{title}"
            metadata = {
                "title": title,
                "author": "Wikipedia",
                "format": "wiki",
                "page_id": page_id,
            }
            try:
                add_chunks(collection, chunks, metadata, source)
                ingested += 1
            except Exception as e:
                print(f"  Error embedding '{title}': {e}")

        # Save progress periodically
        if ingested % 500 == 0:
            save_progress({"last_page_id": page_id, "articles_ingested": ingested, "articles_skipped": skipped})
            print(f"  Ingested {ingested:,} | Skipped {skipped:,} | at '{title}' (page_id {page_id})")

        if limit and ingested >= limit:
            print(f"  Reached limit of {limit} articles.")
            break

    save_progress({"last_page_id": page_id, "articles_ingested": ingested, "articles_skipped": skipped})
    print(f"\nDone. Ingested {ingested:,} articles, skipped {skipped:,}.")

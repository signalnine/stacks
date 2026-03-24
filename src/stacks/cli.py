"""CLI for stacks knowledgebase."""

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from stacks.config import CHAT_MODEL, DEFAULT_TOP_K, EBOOKS_DIR
from stacks.extract import extract, supported_extensions
from stacks.chunker import chunk_text
from stacks.store import get_client, get_collection, add_chunks, search, get_stats, list_sources
from stacks.rag import chat, format_context

console = Console()


@click.group()
def main():
    """Stacks - local knowledgebase with semantic search and RAG."""
    pass


@main.command()
@click.argument("paths", nargs=-1, type=click.Path(exists=True))
@click.option("--recursive", "-r", is_flag=True, help="Recursively scan directories")
def ingest(paths, recursive):
    """Ingest ebooks into the knowledgebase."""
    if not paths:
        console.print("[yellow]No paths specified. Use: stacks ingest /path/to/books[/yellow]")
        return

    files = []
    exts = supported_extensions()
    for p in paths:
        path = Path(p)
        if path.is_file() and path.suffix.lower() in exts:
            files.append(path)
        elif path.is_dir():
            pattern = "**/*" if recursive else "*"
            for f in path.glob(pattern):
                if f.is_file() and f.suffix.lower() in exts:
                    files.append(f)

    if not files:
        console.print("[yellow]No supported files found.[/yellow]")
        console.print(f"Supported formats: {', '.join(sorted(exts))}")
        return

    console.print(f"Found [bold]{len(files)}[/bold] files to ingest.")

    client = get_client()
    collection = get_collection(client)

    # Check what's already ingested
    existing = {s["source"] for s in list_sources(collection)}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Ingesting...", total=len(files))

        for f in files:
            source_key = str(f)
            if source_key in existing:
                progress.update(task, advance=1, description=f"[dim]Skipping (exists): {f.name}[/dim]")
                continue

            progress.update(task, description=f"Extracting: {f.name}")
            try:
                text, metadata = extract(f)
            except Exception as e:
                console.print(f"[red]Failed to extract {f.name}: {e}[/red]")
                progress.update(task, advance=1)
                continue

            if not text.strip():
                console.print(f"[yellow]No text in {f.name}, skipping[/yellow]")
                progress.update(task, advance=1)
                continue

            progress.update(task, description=f"Chunking: {f.name}")
            chunks = chunk_text(text)

            if not chunks:
                progress.update(task, advance=1)
                continue

            progress.update(task, description=f"Embedding {len(chunks)} chunks: {f.name}")
            try:
                add_chunks(collection, chunks, metadata, source_key)
            except Exception as e:
                console.print(f"[red]Failed to embed {f.name}: {e}[/red]")
                progress.update(task, advance=1)
                continue

            progress.update(task, advance=1)

    stats = get_stats(collection)
    console.print(
        f"\n[green]Done.[/green] Knowledgebase: {stats['total_chunks']} chunks from {stats['total_sources']} sources."
    )


@main.command()
@click.argument("query")
@click.option("--top-k", "-k", default=DEFAULT_TOP_K, help="Number of results")
def search_cmd(query, top_k):
    """Semantic search across the knowledgebase."""
    client = get_client()
    collection = get_collection(client)

    if collection.count() == 0:
        console.print("[yellow]Knowledgebase is empty. Run 'stacks ingest' first.[/yellow]")
        return

    results = search(collection, query, top_k=top_k)

    if not results["documents"] or not results["documents"][0]:
        console.print("[yellow]No results found.[/yellow]")
        return

    for i, (doc, meta, dist) in enumerate(
        zip(results["documents"][0], results["metadatas"][0], results["distances"][0])
    ):
        similarity = 1 - dist
        title = meta.get("title", "Unknown")
        author = meta.get("author", "")

        console.print(f"\n[bold cyan]#{i+1}[/bold cyan] [bold]{title}[/bold]", end="")
        if author and author != "Unknown":
            console.print(f" by {author}", end="")
        console.print(f"  [dim](relevance: {similarity:.0%})[/dim]")
        console.print(f"[dim]{meta.get('source', '')}[/dim]")

        # Show a preview
        preview = doc[:300].replace("\n", " ")
        if len(doc) > 300:
            preview += "..."
        console.print(f"{preview}\n")


# Alias so Click doesn't clash with the imported `search` function
search_cmd.name = "search"


@main.command()
@click.option("--model", "-m", default=str(CHAT_MODEL), help="Path to GGUF chat model")
@click.option("--top-k", "-k", default=DEFAULT_TOP_K, help="Number of context chunks")
def ask(model, top_k):
    """Interactive RAG chat with the knowledgebase."""
    client = get_client()
    collection = get_collection(client)

    if collection.count() == 0:
        console.print("[yellow]Knowledgebase is empty. Run 'stacks ingest' first.[/yellow]")
        return

    model_name = Path(model).stem
    console.print(f"[bold]Stacks RAG Chat[/bold] (model: {model_name}, context chunks: {top_k})")
    console.print("[dim]Type 'quit' or Ctrl+C to exit.[/dim]\n")

    history = []

    while True:
        try:
            query = console.input("[bold green]You:[/bold green] ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Bye.[/dim]")
            break

        if not query:
            continue
        if query.lower() in ("quit", "exit", "q"):
            console.print("[dim]Bye.[/dim]")
            break

        console.print("[bold blue]Assistant:[/bold blue] ", end="")

        try:
            response_text = ""
            for chunk in chat(query, model=model, top_k=top_k, history=history):
                delta = chunk["choices"][0].get("delta", {})
                token = delta.get("content", "")
                if token:
                    print(token, end="", flush=True)
                    response_text += token
            print()

            # Keep conversation history (last 10 turns)
            history.append({"role": "user", "content": query})
            history.append({"role": "assistant", "content": response_text})
            if len(history) > 20:
                history = history[-20:]

        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]")

        print()


@main.command()
def stats():
    """Show knowledgebase statistics."""
    client = get_client()
    collection = get_collection(client)

    info = get_stats(collection)

    console.print(f"\n[bold]Knowledgebase Stats[/bold]")
    console.print(f"Total chunks: {info['total_chunks']}")
    console.print(f"Total sources: {info['total_sources']}\n")

    if info["sources"]:
        table = Table(title="Ingested Sources")
        table.add_column("Title", style="cyan")
        table.add_column("Author")
        table.add_column("Format")
        table.add_column("Path", style="dim")

        for s in sorted(info["sources"], key=lambda x: x["title"]):
            table.add_row(s["title"], s["author"], s["format"], s["source"])

        console.print(table)
    else:
        console.print("[yellow]No sources ingested yet.[/yellow]")


@main.command()
@click.argument("source_path")
def remove(source_path):
    """Remove a source from the knowledgebase by path."""
    client = get_client()
    collection = get_collection(client)

    # Find all chunk IDs for this source
    results = collection.get(where={"source": source_path}, include=["metadatas"])
    if not results["ids"]:
        console.print(f"[yellow]No chunks found for: {source_path}[/yellow]")
        return

    collection.delete(ids=results["ids"])
    console.print(f"[green]Removed {len(results['ids'])} chunks for: {source_path}[/green]")


@main.command()
@click.option("--port", "-p", default=8089, help="Server port")
@click.option("--tiles-dir", "-t", default=None, help="Directory containing .pmtiles files")
@click.option("--no-browser", is_flag=True, help="Don't open browser automatically")
def maps(port, tiles_dir, no_browser):
    """Launch the offline maps viewer."""
    from stacks.maps_server import serve_maps
    serve_maps(port=port, tiles_dir=tiles_dir, no_browser=no_browser)


# --- Wikipedia commands ---

@main.group()
def wiki():
    """Wikipedia dump: download, filter, and ingest."""
    pass


@wiki.command()
def download():
    """Download the English Wikipedia articles dump (~22GB)."""
    from stacks.wiki import download_dump
    console.print("[bold]Downloading Wikipedia dump...[/bold]")
    console.print("This is ~22GB compressed. Supports resume if interrupted.\n")
    path = download_dump()
    console.print(f"\n[green]Saved to:[/green] {path}")


@wiki.command("build-categories")
@click.option("--force", is_flag=True, help="Rebuild even if cache exists")
def build_categories(force):
    """Build category hierarchy from the dump (pass 1)."""
    from stacks.wiki import get_dump_path, build_category_graph, build_exclusion_set

    dump = get_dump_path()
    if not dump.exists():
        console.print("[red]Dump not found. Run 'stacks wiki download' first.[/red]")
        return

    graph = build_category_graph(dump, force=force)
    exclusion = build_exclusion_set(graph)
    console.print(f"\n[green]Category graph:[/green] {len(graph):,} categories")
    console.print(f"[green]Excluded:[/green] {len(exclusion):,} categories (pop culture + subcategories)")


@wiki.command("show-exclusions")
def show_exclusions():
    """Show the root categories being excluded."""
    from stacks.wiki import EXCLUDE_ROOTS
    console.print("[bold]Excluded root categories:[/bold]\n")
    for cat in sorted(EXCLUDE_ROOTS):
        console.print(f"  - {cat}")
    console.print(f"\n{len(EXCLUDE_ROOTS)} roots (subcategories are crawled automatically)")


@wiki.command()
@click.option("--limit", "-n", default=None, type=int, help="Max articles to ingest (for testing)")
@click.option("--no-resume", is_flag=True, help="Start from scratch, ignore saved progress")
def ingest_wiki(limit, no_resume):
    """Filter and ingest Wikipedia articles (pass 2)."""
    from stacks.wiki import (
        get_dump_path, build_category_graph, build_exclusion_set,
        ingest_wiki as do_ingest,
    )

    dump = get_dump_path()
    if not dump.exists():
        console.print("[red]Dump not found. Run 'stacks wiki download' first.[/red]")
        return

    console.print("[bold]Loading category graph...[/bold]")
    graph = build_category_graph(dump)
    exclusion = build_exclusion_set(graph)

    console.print(f"\n[bold]Ingesting filtered Wikipedia articles...[/bold]")
    if limit:
        console.print(f"[dim]Limit: {limit} articles[/dim]")
    console.print()

    do_ingest(dump, exclusion, resume=not no_resume, limit=limit)

    stats = get_stats(get_collection(get_client()))
    console.print(
        f"\n[green]Knowledgebase:[/green] {stats['total_chunks']:,} chunks from {stats['total_sources']:,} sources."
    )


@wiki.command()
def status():
    """Show Wikipedia ingest progress."""
    from stacks.wiki import load_progress, get_dump_path, CATEGORY_CACHE

    dump = get_dump_path()
    console.print("[bold]Wikipedia Ingest Status[/bold]\n")

    if dump.exists():
        size_gb = dump.stat().st_size / 1e9
        console.print(f"Dump file: {dump} ({size_gb:.1f} GB)")
    else:
        console.print("[yellow]Dump not downloaded yet.[/yellow]")

    if CATEGORY_CACHE.exists():
        import json
        data = json.loads(CATEGORY_CACHE.read_text())
        console.print(f"Category graph: {len(data):,} categories (cached)")
    else:
        console.print("[yellow]Category graph not built yet.[/yellow]")

    progress = load_progress()
    if progress["last_page_id"]:
        console.print(f"\nIngest progress:")
        console.print(f"  Last page ID: {progress['last_page_id']}")
        console.print(f"  Articles ingested: {progress['articles_ingested']:,}")
        console.print(f"  Articles skipped: {progress['articles_skipped']:,}")
    else:
        console.print("\n[yellow]No ingest progress yet.[/yellow]")


if __name__ == "__main__":
    main()

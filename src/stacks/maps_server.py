"""Simple local server for the maps viewer + PMTiles files."""

import http.server
import functools
import webbrowser
from pathlib import Path

import click
from rich.console import Console

console = Console()

MAPS_DIR = Path(__file__).parent.parent.parent / "maps"


class CORSHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler that serves files with CORS and proper MIME types."""

    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".pmtiles": "application/octet-stream",
        ".pbf": "application/x-protobuf",
    }

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Range")
        self.send_header("Access-Control-Expose-Headers", "Content-Range, Content-Length")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def log_message(self, format, *args):
        # Quiet logging
        pass


def serve_maps(port: int = 8089, tiles_dir: str | None = None, no_browser: bool = False):
    """Start the maps server."""
    # Serve from the maps/ directory, with tiles_dir as a symlink or extra path
    serve_dir = str(MAPS_DIR)

    if tiles_dir:
        tiles_path = Path(tiles_dir)
        if tiles_path.exists():
            # Symlink the tiles directory into maps/tiles
            link = MAPS_DIR / "tiles"
            if link.is_symlink():
                link.unlink()
            if not link.exists():
                link.symlink_to(tiles_path.resolve())
                console.print(f"Linked tiles: {tiles_path} -> {link}")

    handler = functools.partial(CORSHandler, directory=serve_dir)
    server = http.server.HTTPServer(("127.0.0.1", port), handler)

    url = f"http://localhost:{port}"
    console.print(f"[bold green]Stacks Maps[/bold green] serving at [link={url}]{url}[/link]")
    console.print(f"Serving files from: {serve_dir}")
    if tiles_dir:
        console.print(f"PMTiles directory: {tiles_dir}")
        console.print(f"Load tiles via: {url}?url=tiles/YOUR_FILE.pmtiles")
    console.print("[dim]Ctrl+C to stop[/dim]\n")

    if not no_browser:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        console.print("\n[dim]Server stopped.[/dim]")
        server.server_close()

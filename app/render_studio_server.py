"""
Local Range-enabled HTTP streaming server for Video Render Studio.
Serves static UI files, video streams with HTTP 206 Partial Content (range requests),
and thumbnails seamlessly to pywebview WKWebView on macOS.
"""

from __future__ import annotations

import mimetypes
import os
import re
import socket
import threading
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import unquote, urlparse

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = Path(__file__).resolve().parent


def find_free_port(starting_port: int = 49152) -> int:
    """Find an available TCP port on localhost."""
    for port in range(starting_port, starting_port + 200):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return 0


class RangeHTTPRequestHandler(SimpleHTTPRequestHandler):
    """HTTP Request Handler that supports HTTP 206 Partial Content (Byte Range requests)."""

    def end_headers(self):
        # Enable CORS for pywebview
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Range, Content-Type")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def translate_path(self, path: str) -> str:
        """Map URL paths to filesystem paths."""
        parsed = urlparse(path)
        clean_path = unquote(parsed.path)

        # Route /media?path=<absolute_or_relative_path>
        if clean_path.startswith("/media"):
            query_str = parsed.query
            for param in query_str.split("&"):
                if param.startswith("path="):
                    target = unquote(param[5:])
                    target_path = Path(target)
                    if not target_path.is_absolute():
                        target_path = PROJECT_ROOT / target_path
                    return str(target_path.resolve())

        # Route /ui/... to app/ directory
        if clean_path.startswith("/ui/"):
            rel = clean_path[4:]
            return str((APP_DIR / rel).resolve())

        # Default fallback to PROJECT_ROOT
        rel = clean_path.lstrip("/")
        if not rel or rel == "index.html":
            return str((APP_DIR / "render_studio.html").resolve())

        return str((PROJECT_ROOT / rel).resolve())

    def do_GET(self):
        """Handle GET requests with full Range / 206 Partial Content support."""
        path = self.translate_path(self.path)
        if not os.path.exists(path) or os.path.isdir(path):
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return

        range_header = self.headers.get("Range")
        if not range_header:
            # Standard full file request
            return super().do_GET()

        # Parse Range header: bytes=START-END
        match = re.match(r"^bytes=(\d*)-(\d*)$", range_header.strip())
        if not match:
            return super().do_GET()

        total_size = os.path.getsize(path)
        start_str, end_str = match.groups()

        start = int(start_str) if start_str else 0
        end = int(end_str) if end_str else total_size - 1

        if start >= total_size or end >= total_size or start > end:
            self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
            self.send_header("Content-Range", f"bytes */{total_size}")
            self.end_headers()
            return

        length = end - start + 1
        content_type, _ = mimetypes.guess_type(path)
        if not content_type:
            content_type = "application/octet-stream"

        self.send_response(HTTPStatus.PARTIAL_CONTENT)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Range", f"bytes {start}-{end}/{total_size}")
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()

        try:
            with open(path, "rb") as f:
                f.seek(start)
                bytes_to_send = length
                chunk_size = 64 * 1024
                while bytes_to_send > 0:
                    read_len = min(chunk_size, bytes_to_send)
                    data = f.read(read_len)
                    if not data:
                        break
                    self.wfile.write(data)
                    bytes_to_send -= len(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, format: str, *args):
        # Suppress noisy standard HTTP logs in stdout
        pass


class LocalMediaServer:
    """Manages the background HTTP streaming server instance."""

    def __init__(self, port: Optional[int] = None):
        self.port = port or find_free_port()
        self.server: Optional[ThreadingHTTPServer] = None
        self.thread: Optional[threading.Thread] = None

    def start(self) -> str:
        self.server = ThreadingHTTPServer(("127.0.0.1", self.port), RangeHTTPRequestHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return f"http://127.0.0.1:{self.port}"

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()

    def get_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def get_media_url(self, file_path: str) -> str:
        from urllib.parse import quote
        return f"http://127.0.0.1:{self.port}/media?path={quote(file_path)}"

#!/usr/bin/env python3
"""
Video Render Studio Launcher.
Runs the Range-enabled local streaming media server and opens the native macOS PyWebView window.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import webview

APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from render_studio_api import RenderStudioAPI
from render_studio_server import LocalMediaServer


def parse_args():
    parser = argparse.ArgumentParser(description="Launch Video Render Studio & Sequencer (pywebview)")
    parser.add_argument("--port", type=int, default=None, help="Custom port for internal streaming server")
    parser.add_argument("--debug", action="store_true", help="Enable WebKit developer inspector")
    return parser.parse_args()


def main():
    args = parse_args()
    server = LocalMediaServer(port=args.port)
    server_url = server.start()

    api = RenderStudioAPI(server=server)

    window = webview.create_window(
        title="Video Render Studio & Sequencer",
        url=f"{server_url}/ui/render_studio.html",
        js_api=api,
        width=1320,
        height=840,
        min_size=(1060, 680),
        background_color="#06070a",
        text_select=False,
    )
    api.set_window(window)

    try:
        webview.start(debug=args.debug)
    finally:
        server.stop()


if __name__ == "__main__":
    main()

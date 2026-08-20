"""
JavaScript API Bridge for Video Render Studio.
Connects webview frontend interactions to backend FFmpeg operations.
"""

from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

import webview

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import render_studio_backend as backend


class RenderStudioAPI:
    """JS Bridge exposed to pywebview window."""

    def __init__(self, server=None):
        self._window: Optional[webview.Window] = None
        self._server = server
        self._is_rendering = False

    def set_window(self, window: webview.Window):
        self._window = window

    def set_server(self, server):
        self._server = server

    def log(self, text: str, log_type: str = "info"):
        """Send live log output to frontend console drawer."""
        if self._window:
            safe_text = json.dumps(text)
            self._window.evaluate_js(f"window.appendRenderLog && window.appendRenderLog({safe_text}, '{log_type}')")

    def notify_progress(self, progress_pct: int, status_text: str):
        """Update progress bar in frontend."""
        if self._window:
            safe_status = json.dumps(status_text)
            self._window.evaluate_js(
                f"window.updateRenderProgress && window.updateRenderProgress({progress_pct}, {safe_status})"
            )

    def get_initial_data(self) -> Dict[str, Any]:
        """Fetch scanned videos, all project files, and initial configuration."""
        videos = self.scan_videos()
        all_files = self.scan_all_files()
        output_dir = backend.OUTPUT_DIR
        return {
            "workspace_root": str(PROJECT_ROOT),
            "output_dir": str(output_dir),
            "videos": videos,
            "all_files": all_files,
            "server_url": self._server.get_url() if self._server else "",
        }

    def scan_videos(self) -> List[Dict[str, Any]]:
        """Scan repository and enrich with HTTP streaming URLs."""
        raw_videos = backend.list_available_videos()
        enriched = []
        for v in raw_videos:
            v_copy = dict(v)
            if self._server:
                v_copy["stream_url"] = self._server.get_media_url(v["path"])
                if v.get("thumbnail_path") and os.path.exists(v["thumbnail_path"]):
                    v_copy["thumb_url"] = self._server.get_media_url(v["thumbnail_path"])
                else:
                    v_copy["thumb_url"] = ""
            else:
                v_copy["stream_url"] = f"file://{v['path']}"
                v_copy["thumb_url"] = f"file://{v['thumbnail_path']}" if v.get("thumbnail_path") else ""
            enriched.append(v_copy)
        return enriched

    def scan_all_files(self) -> List[Dict[str, Any]]:
        """Scan entire project directory and enrich media URLs."""
        raw_files = backend.list_all_project_files()
        enriched = []
        for f in raw_files:
            f_copy = dict(f)
            if self._server:
                f_copy["stream_url"] = self._server.get_media_url(f["path"])
                if f.get("thumbnail_path") and os.path.exists(f["thumbnail_path"]):
                    f_copy["thumb_url"] = self._server.get_media_url(f["thumbnail_path"])
                elif f.get("file_type") == "image":
                    f_copy["thumb_url"] = self._server.get_media_url(f["path"])
                else:
                    f_copy["thumb_url"] = ""
            else:
                f_copy["stream_url"] = f"file://{f['path']}"
                f_copy["thumb_url"] = f"file://{f['thumbnail_path']}" if f.get("thumbnail_path") else ""
            enriched.append(f_copy)
        return enriched

    def read_file_content(self, file_path: str) -> Dict[str, Any]:
        """Read and return content of any text/code/markdown/json project file."""
        return backend.read_project_file_content(file_path)


    def pick_video_file(self) -> Optional[Dict[str, Any]]:
        """Open native macOS file dialog to import an external video."""
        if not self._window:
            return None
        result = self._window.create_file_dialog(
            webview.OPEN_DIALOG,
            directory=str(PROJECT_ROOT),
            file_types=("Video Files (*.mp4;*.mov;*.mkv;*.webm;*.m4v)", "All Files (*.*)"),
        )
        if result and len(result) > 0:
            picked_path = Path(result[0]).resolve()
            if picked_path.is_file():
                try:
                    info = backend.get_media_info(picked_path)
                    thumb_path = backend.generate_thumbnail(picked_path)
                    info["thumbnail_path"] = thumb_path
                    try:
                        rel_path = str(picked_path.relative_to(PROJECT_ROOT))
                    except ValueError:
                        rel_path = str(picked_path)
                    info["relative_path"] = rel_path
                    rel_parent = str(Path(rel_path).parent)
                    info["folder_path"] = "" if rel_parent == "." else rel_parent
                    info["folder_parts"] = [p for p in Path(rel_path).parent.parts if p != "."]
                    info["category"] = "Imported Files"

                    if self._server:
                        info["stream_url"] = self._server.get_media_url(str(picked_path))
                        info["thumb_url"] = self._server.get_media_url(thumb_path) if thumb_path else ""
                    else:
                        info["stream_url"] = f"file://{picked_path}"
                        info["thumb_url"] = f"file://{thumb_path}" if thumb_path else ""
                    return info
                except Exception as exc:
                    self.log(f"Error importing video: {exc}", "error")
                    return None
        return None

    def pick_watermark_file(self) -> Optional[str]:
        """Open native macOS file dialog to select a watermark image."""
        if not self._window:
            return None
        result = self._window.create_file_dialog(
            webview.OPEN_DIALOG,
            directory=str(PROJECT_ROOT),
            file_types=("Image Files (*.png;*.jpg;*.jpeg;*.webp)", "All Files (*.*)"),
        )
        if result and len(result) > 0:
            return result[0]
        return None

    def start_export(self, timeline_json_str: str, options_json_str: str) -> None:
        """Start async export of the sequence."""
        if self._is_rendering:
            self.log("A render job is already in progress.", "error")
            return

        try:
            timeline_items = json.loads(timeline_json_str)
            options = json.loads(options_json_str) if options_json_str else {}
        except Exception as e:
            self.log(f"Failed to parse export parameters: {e}", "error")
            return

        def _worker():
            self._is_rendering = True
            self.notify_progress(5, "Initializing render pipeline...")
            try:
                out_filename = options.get("filename", "")
                resolution = options.get("resolution", "1080p")
                fps = float(options.get("fps", 30.0))
                watermark = options.get("watermark_path", None)

                # Parse resolution
                w, h = 1920, 1080
                if resolution == "720p":
                    w, h = 1280, 720
                elif resolution == "4k":
                    w, h = 3840, 2160
                elif resolution == "auto" and timeline_items:
                    first_clip = next((i for i in timeline_items if i.get("type") != "break"), None)
                    if first_clip and first_clip.get("path"):
                        try:
                            probe = backend.get_media_info(Path(first_clip["path"]))
                            w, h = probe["width"], probe["height"]
                        except Exception:
                            w, h = 1920, 1080

                total_items = len(timeline_items)

                def log_cb(msg: str, msg_type: str = "info"):
                    self.log(msg, msg_type)

                # Execute backend render
                result_info = backend.render_sequence(
                    timeline_items=timeline_items,
                    output_filename=out_filename,
                    target_width=w,
                    target_height=h,
                    target_fps=fps,
                    watermark_image=watermark,
                    log_callback=log_cb,
                )

                self.notify_progress(100, "Render complete!")
                if self._window:
                    safe_res = json.dumps(result_info)
                    self._window.evaluate_js(f"window.onRenderSuccess && window.onRenderSuccess({safe_res})")

            except Exception as exc:
                self.log(f"❌ Render failed: {exc}", "error")
                self.notify_progress(0, f"Error: {exc}")
                if self._window:
                    safe_err = json.dumps(str(exc))
                    self._window.evaluate_js(f"window.onRenderError && window.onRenderError({safe_err})")
            finally:
                self._is_rendering = False

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

    def open_output_folder(self) -> None:
        """Reveal output folder in Finder."""
        backend.open_in_finder(str(backend.OUTPUT_DIR))

    def reveal_file(self, file_path: str) -> None:
        """Reveal specific file in Finder."""
        backend.open_in_finder(file_path)

    def play_video(self, file_path: str) -> None:
        """Launch video in macOS player."""
        backend.play_video(file_path)

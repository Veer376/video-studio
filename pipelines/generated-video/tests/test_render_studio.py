#!/usr/bin/env python3
"""
Unit tests for Video Render Studio & Sequencer backend.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
APP_DIR = PROJECT_ROOT / "app"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import render_studio_backend as backend
from render_studio_server import LocalMediaServer


class TestRenderStudio(unittest.TestCase):
    def setUp(self):
        backend.ensure_dirs()
        self.temp_dir = tempfile.TemporaryDirectory(prefix="test-render-studio-")
        self.temp_path = Path(self.temp_dir.name)

        # Create two minimal synthetic MP4 clips for testing
        self.clip1 = self.temp_path / "clip1.mp4"
        self.clip2 = self.temp_path / "clip2.mp4"

        backend.build_synthetic_break(
            duration=3.0,
            width=640,
            height=360,
            fps=30.0,
            out_path=self.clip1,
            color="red",
        )
        backend.build_synthetic_break(
            duration=4.0,
            width=640,
            height=360,
            fps=30.0,
            out_path=self.clip2,
            color="blue",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_media_info_extraction(self):
        info = backend.get_media_info(self.clip1)
        self.assertEqual(info["filename"], "clip1.mp4")
        self.assertAlmostEqual(info["duration"], 3.0, delta=0.2)
        self.assertEqual(info["width"], 640)
        self.assertEqual(info["height"], 360)
        self.assertTrue(info["has_audio"])

    def test_synthetic_break_creation(self):
        break_path = self.temp_path / "break.mp4"
        backend.build_synthetic_break(
            duration=1.5,
            width=1280,
            height=720,
            fps=30.0,
            out_path=break_path,
            color="black",
        )
        self.assertTrue(break_path.is_file())
        info = backend.get_media_info(break_path)
        self.assertAlmostEqual(info["duration"], 1.5, delta=0.2)
        self.assertEqual(info["width"], 1280)
        self.assertEqual(info["height"], 720)

    def test_thumbnail_generation(self):
        thumb = backend.generate_thumbnail(self.clip1, force=True)
        self.assertTrue(Path(thumb).is_file())
        self.assertTrue(Path(thumb).stat().st_size > 0)

    def test_normalize_and_trim_clip(self):
        trimmed = self.temp_path / "trimmed.mp4"
        # Trim from 1.0s to 2.5s (1.5s duration)
        backend.normalize_and_trim_clip(
            src_path=self.clip1,
            start_sec=1.0,
            end_sec=2.5,
            width=1280,
            height=720,
            fps=30.0,
            out_path=trimmed,
        )
        self.assertTrue(trimmed.is_file())
        info = backend.get_media_info(trimmed)
        self.assertAlmostEqual(info["duration"], 1.5, delta=0.2)
        self.assertEqual(info["width"], 1280)
        self.assertEqual(info["height"], 720)

    def test_render_full_sequence_with_breaks(self):
        timeline = [
            {
                "type": "clip",
                "path": str(self.clip1),
                "start": 0.5,
                "end": 2.5, # 2.0s
            },
            {
                "type": "break",
                "duration": 1.0, # 1.0s
                "color": "black",
            },
            {
                "type": "clip",
                "path": str(self.clip2),
                "start": 1.0,
                "end": 3.0, # 2.0s
            },
        ]

        out_name = "test_sequenced_render.mp4"
        logs = []

        def log_cb(msg, mtype):
            logs.append((msg, mtype))

        result = backend.render_sequence(
            timeline_items=timeline,
            output_filename=out_name,
            target_width=1280,
            target_height=720,
            target_fps=30.0,
            log_callback=log_cb,
        )

        out_file = backend.OUTPUT_DIR / out_name
        self.assertTrue(out_file.is_file())
        self.assertAlmostEqual(result["duration"], 5.0, delta=0.4)
        self.assertEqual(result["width"], 1280)
        self.assertEqual(result["height"], 720)
        self.assertTrue(len(logs) > 0)

        # Cleanup test output
        if out_file.exists():
            out_file.unlink()

    def test_range_streaming_server(self):
        server = LocalMediaServer()
        base_url = server.start()
        try:
            # Request video file with Range header
            media_url = server.get_media_url(str(self.clip1))
            req = Request(media_url, headers={"Range": "bytes=0-100"})
            with urlopen(req) as resp:
                self.assertEqual(resp.status, 206)
                data = resp.read()
                self.assertEqual(len(data), 101)
                self.assertIn("bytes 0-100/", resp.headers.get("Content-Range", ""))
        finally:
            server.stop()

    def test_list_all_project_files(self):
        # Create sample md and py files in temp directory
        md_file = self.temp_path / "sample.md"
        md_file.write_text("# Hello World\nThis is markdown.", encoding="utf-8")

        py_file = self.temp_path / "script.py"
        py_file.write_text("print('hello')", encoding="utf-8")

        files = backend.list_all_project_files(custom_root=self.temp_path)
        self.assertTrue(len(files) >= 4)  # 2 clips + 1 md + 1 py

        types = {f["file_type"] for f in files}
        self.assertIn("video", types)
        self.assertIn("markdown", types)
        self.assertIn("python", types)

    def test_read_project_file_content(self):
        md_file = self.temp_path / "test_doc.md"
        md_file.write_text("# Title\nLine 2\nLine 3", encoding="utf-8")

        data = backend.read_project_file_content(str(md_file))
        self.assertEqual(data["filename"], "test_doc.md")
        self.assertEqual(data["file_type"], "markdown")
        self.assertEqual(data["lines_count"], 3)
        self.assertIn("# Title", data["content"])

    def test_project_path_categories_support_canonical_and_legacy_roots(self):
        self.assertEqual(
            backend._categorize_path("projects/demo/videos/s001.mp4"),
            "Project: demo",
        )
        self.assertEqual(
            backend._categorize_path("stories/legacy/videos/s001.mp4"),
            "Project: legacy",
        )


if __name__ == "__main__":
    unittest.main()

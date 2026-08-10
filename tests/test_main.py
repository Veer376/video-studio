from __future__ import annotations

import base64
import tempfile
import unittest
from pathlib import Path

from main import video_input, video_response_format


class VideoInputTests(unittest.TestCase):
    def test_mp4_is_encoded_as_inline_video(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            video = Path(temporary_directory) / "clip.mp4"
            video.write_bytes(b"video-bytes")

            content = video_input(video)

            self.assertEqual(content["type"], "video")
            self.assertEqual(content["mime_type"], "video/mp4")
            self.assertEqual(base64.b64decode(content["data"]), b"video-bytes")

    def test_edit_response_format_omits_aspect_ratio(self) -> None:
        self.assertEqual(video_response_format("edit", "16:9"), {"type": "video"})

    def test_generation_response_format_includes_aspect_ratio(self) -> None:
        self.assertEqual(
            video_response_format("reference_to_video", "16:9"),
            {"type": "video", "aspect_ratio": "16:9"},
        )


if __name__ == "__main__":
    unittest.main()

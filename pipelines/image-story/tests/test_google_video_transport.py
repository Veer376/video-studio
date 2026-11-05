"""Mocked Google optional-video request boundaries."""
import base64
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from scripts.production.providers import GoogleVideoProvider


class GoogleVideoTransportTests(unittest.TestCase):
    def test_requested_duration_and_two_frame_inputs_are_transmitted(self):
        client = Mock()
        client.interactions.create.return_value = SimpleNamespace(
            output_video=SimpleNamespace(data=base64.b64encode(b"fixture").decode()))
        with tempfile.TemporaryDirectory() as tmp:
            start, end, output = (Path(tmp) / name for name in ("start.png", "end.png", "clip.mp4"))
            start.write_bytes(b"start")
            end.write_bytes(b"end")
            provider = GoogleVideoProvider()
            provider._client = client
            provider.generate(prompt="Move between frames.", start_frame=start, end_frame=end,
                              output=output, aspect_ratio="16:9", model="omni_flash", duration=4)
            request = client.interactions.create.call_args.kwargs
            self.assertEqual(request["model"], "gemini-omni-1.1-flash")
            self.assertEqual(request["response_format"],
                             {"type": "video", "aspect_ratio": "16:9", "duration": "4s", "resolution": "720p"})
            self.assertEqual([x["type"] for x in request["input"]], ["image", "image", "text"])
            self.assertEqual(output.read_bytes(), b"fixture")

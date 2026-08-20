import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from studio.rendering import final


class FinalRenderTests(unittest.TestCase):
    def test_force_replaces_canonical_output(self) -> None:
        with TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "temp").mkdir()
            (project / "audio").mkdir()
            (project / "output").mkdir()
            (project / "temp" / "video-no-audio.mp4").write_bytes(b"video")
            (project / "audio" / "narration.wav").write_bytes(b"audio")
            (project / "session.json").write_text(
                json.dumps({"session": {"status": "storyboard_complete"}}),
                encoding="utf-8",
            )
            canonical = project / "output" / "final-video.mp4"
            canonical.write_bytes(b"old")

            def fake_ffmpeg(*args: str) -> None:
                Path(args[-1]).write_bytes(b"new")

            with (
                patch.object(final.shutil, "which", return_value="/usr/bin/tool"),
                patch.object(final, "get_duration", return_value=10.0),
                patch.object(final, "run_ffmpeg", side_effect=fake_ffmpeg),
            ):
                final.main(["--project-dir", str(project), "--force"])

            self.assertEqual(b"new", canonical.read_bytes())
            self.assertEqual([], list((project / "output").glob("final-video-*.mp4")))

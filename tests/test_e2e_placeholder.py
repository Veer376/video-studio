import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from story_video.cli import main
from story_video.ffmpeg import probe_duration, video_has_stream


class PlaceholderE2ETests(unittest.TestCase):
    def test_e2e_placeholder_build(self):
        with TemporaryDirectory() as temp_dir:
            tmp_path = Path(temp_dir)
            manifest = {
                "project": {"title": "test", "language": "hi-IN", "aspect_ratio": "16:9", "resolution": "320x180", "fps": 15},
                "voice": {"provider": "existing_audio"},
                "scenes": [
                    {
                        "id": "scene-001",
                        "narration": "पहला दृश्य",
                        "image_prompt": "placeholder one",
                        "image_path": "generated/images/scene-001.png",
                        "audio_path": "generated/audio/scene-001.wav",
                        "subtitle": "पहला दृश्य",
                        "motion": {"type": "slow_zoom_in", "intensity": 0.02},
                        "transition": {"type": "crossfade", "duration_seconds": 0.2},
                    },
                    {
                        "id": "scene-002",
                        "narration": "दूसरा दृश्य",
                        "image_prompt": "placeholder two",
                        "image_path": "generated/images/scene-002.png",
                        "audio_path": "generated/audio/scene-002.wav",
                        "subtitle": "दूसरा दृश्य",
                        "motion": {"type": "slow_pan_right", "intensity": 0.02},
                        "transition": {"type": "crossfade", "duration_seconds": 0.2},
                    },
                ],
            }
            path = tmp_path / "story.json"
            path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

            self.assertEqual(main(["build", str(path), "--placeholder-assets"]), 0)
            output = tmp_path / "output/final-video.mp4"
            self.assertTrue(output.exists())
            self.assertTrue(video_has_stream(output))
            self.assertGreater(probe_duration(output), 5.0)

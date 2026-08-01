from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from studio.core.state import illustrate_state, voice_state


class StudioStateTests(unittest.TestCase):
    def test_voice_state_requires_audio_timestamps_and_scene_times(self):
        with TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            (project_dir / "audio").mkdir()
            (project_dir / "audio" / "narration.wav").write_bytes(b"wav")
            (project_dir / "scenes.json").write_text(
                json.dumps(
                    {
                        "scenes": [
                            {
                                "id": "scene-001",
                                "start_time": 0.0,
                                "end_time": None,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            state = voice_state(project_dir)

        self.assertFalse(state.complete)
        self.assertIn("audio/timestamps.json", state.missing)
        self.assertIn("scene-001.end_time", state.missing)

    def test_illustrate_state_accepts_existing_scene_images(self):
        with TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            (project_dir / "images").mkdir()
            (project_dir / "images" / "scene-001.png").write_bytes(b"png")
            (project_dir / "scenes.json").write_text(
                json.dumps(
                    {
                        "scenes": [
                            {
                                "id": "scene-001",
                                "image_path": "images/scene-001.png",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            state = illustrate_state(project_dir)

        self.assertTrue(state.complete)
        self.assertEqual((), state.missing)

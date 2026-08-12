from pathlib import Path
from tempfile import TemporaryDirectory
import io
import json
import unittest
from unittest.mock import patch

from PIL import Image

from studio.core import paths as studio_paths
from studio.core.state import illustrate_state, voice_state


def png_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (8, 8), (20, 40, 60)).save(output, format="PNG")
    return output.getvalue()


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
            (project_dir / "images" / "scene-001.png").write_bytes(png_bytes())
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

    def test_illustrate_state_requires_registered_character_asset(self):
        with TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            (project_dir / "images").mkdir()
            (project_dir / "images" / "scene-001.png").write_bytes(png_bytes())
            (project_dir / "scenes.json").write_text(
                json.dumps(
                    {
                        "characters": {
                            "hero": {
                                "canonical_name": "Hero",
                                "prompt": "a hero",
                                "image_path": "assets/characters/hero.png",
                            }
                        },
                        "scenes": [
                            {"id": "scene-001", "image_path": "images/scene-001.png"}
                        ],
                    }
                ),
                encoding="utf-8",
            )

            state = illustrate_state(project_dir)

        self.assertFalse(state.complete)
        self.assertIn("assets/characters/hero.png", state.missing)

    def test_illustrate_state_accepts_valid_shared_root_character_asset(self):
        with TemporaryDirectory() as tmp:
            repository = Path(tmp) / "repository"
            project_dir = repository / "library" / "story"
            shared = repository / "assets" / "characters" / "hero.png"
            shared.parent.mkdir(parents=True)
            shared.write_bytes(png_bytes())
            (project_dir / "images").mkdir(parents=True)
            (project_dir / "images" / "scene-001.png").write_bytes(png_bytes())
            (project_dir / "scenes.json").write_text(
                json.dumps(
                    {
                        "characters": {
                            "hero": {
                                "canonical_name": "Hero",
                                "prompt": None,
                                "image_path": "root:assets/characters/hero.png",
                            }
                        },
                        "scenes": [
                            {"id": "scene-001", "image_path": "images/scene-001.png"}
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with patch.object(studio_paths, "project_root", return_value=repository):
                state = illustrate_state(project_dir)

        self.assertTrue(state.complete)

    def test_illustrate_state_requires_adaptation_for_root_asset_with_prompt(self):
        with TemporaryDirectory() as tmp:
            repository = Path(tmp) / "repository"
            project_dir = repository / "library" / "story"
            shared = repository / "assets" / "characters" / "hero.jpg"
            shared.parent.mkdir(parents=True)
            shared.write_bytes(png_bytes())
            (project_dir / "images").mkdir(parents=True)
            (project_dir / "images" / "scene-001.png").write_bytes(png_bytes())
            (project_dir / "scenes.json").write_text(
                json.dumps(
                    {
                        "characters": {
                            "hero": {
                                "canonical_name": "Hero",
                                "prompt": "a hero in a blue robe",
                                "image_path": "root:assets/characters/hero.jpg",
                            }
                        },
                        "scenes": [
                            {"id": "scene-001", "image_path": "images/scene-001.png"}
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with patch.object(studio_paths, "project_root", return_value=repository):
                state = illustrate_state(project_dir)

        self.assertFalse(state.complete)
        self.assertIn("characters.hero.root_adaptation", state.missing)

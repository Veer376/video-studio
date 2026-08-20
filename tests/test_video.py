from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.video import (
    BaseProvider,
    CharacterEntry,
    FlowProvider,
    GoogleProvider,
    VideoError,
    compile_scene,
    format_character_brief,
    get_provider,
    load_characters,
)


class VideoPackageTests(unittest.TestCase):
    def test_get_provider_factory(self) -> None:
        google_p = get_provider("google")
        self.assertIsInstance(google_p, GoogleProvider)
        self.assertEqual(google_p.name, "google")

        flow_p = get_provider("flow")
        self.assertIsInstance(flow_p, FlowProvider)
        self.assertEqual(flow_p.name, "flow")

        with self.assertRaises(ValueError):
            get_provider("unsupported_provider")

    def test_two_tier_character_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            img1 = root / "chhotu.png"
            img2 = root / "custom.png"
            img1.write_bytes(b"chhotu")
            img2.write_bytes(b"custom")

            # Global registry
            global_json = root / "characters.json"
            global_json.write_text(json.dumps({
                "characters": [
                    {
                        "handle": "@chhotu",
                        "name": "Global Chhotu",
                        "reference_path": "chhotu.png",
                        "profile": "Age: 10; Voice: fast",
                        "description": "Young inventor",
                    }
                ]
            }))

            # Story registry overriding handle
            story_dir = root / "stories" / "demo"
            story_dir.mkdir(parents=True)
            story_json = story_dir / "characters.json"
            story_json.write_text(json.dumps({
                "characters": [
                    {
                        "handle": "@chhotu",
                        "name": "Story Chhotu",
                        "reference_path": "custom.png",
                    },
                    {
                        "handle": "@hero",
                        "name": "Story Hero",
                        "reference_path": "custom.png",
                        "profile": "Age: 20",
                    }
                ]
            }))

            chars = load_characters(root, story_json)
            self.assertIn("@chhotu", chars)
            self.assertIn("@hero", chars)
            # Story override verified
            self.assertEqual(chars["@chhotu"].name, "Story Chhotu")
            self.assertEqual(chars["@chhotu"].resolved_reference_path, img2)
            # Global profile inherited
            self.assertEqual(chars["@chhotu"].profile, "Age: 10; Voice: fast")

    def test_format_character_brief(self) -> None:
        chars = {
            "@chhotu": CharacterEntry(
                handle="@chhotu",
                name="Chhotu",
                reference_path="chhotu.png",
                resolved_reference_path=Path("/tmp/chhotu.png"),
                profile="Age: 10",
                description="Leader",
            )
        }
        brief = format_character_brief(["@chhotu"], chars)
        self.assertIn("CHARACTER PROFILES:", brief)
        self.assertIn("- @chhotu (Chhotu):", brief)
        self.assertIn("  Profile: Age: 10", brief)
        self.assertIn("  Description: Leader", brief)

    def test_compile_scene_with_annotated_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            img = root / "chhotu.png"
            img.write_bytes(b"chhotu")
            chars = {
                "@chhotu": CharacterEntry(
                    handle="@chhotu",
                    name="Chhotu",
                    reference_path="chhotu.png",
                    resolved_reference_path=img,
                    profile="Age: 10 child",
                    description="Leader",
                )
            }
            scene = {
                "id": "s001",
                "prompt": "@chhotu jumps high in the sky.",
                "subjects": ["@chhotu"],
            }
            compiled = compile_scene(scene, chars, root)
            self.assertIn("<IMAGE_REF_0> jumps high", compiled.prompt)
            self.assertIn("@chhotu (Age: 10 child) jumps high", compiled.annotated_prompt)


if __name__ == "__main__":
    unittest.main()

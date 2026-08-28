"""Tests for canonical video-project initialization."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.project import ProjectSetupError, create_project, derive_slug


class StoryProjectTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_create_project_writes_canonical_structure(self) -> None:
        result = create_project(
            self.root,
            title="Flying Auto",
            aspect_ratio="9:16",
        )

        project = self.root / "stories" / "flying-auto"
        self.assertEqual(result["status"], "created")
        self.assertEqual(result["project"]["slug"], "flying-auto")
        self.assertEqual(result["next_action"], "plan_story")
        self.assertTrue((project / "story.md").is_file())
        self.assertEqual(
            json.loads((project / "characters.json").read_text(encoding="utf-8")),
            {"characters": []},
        )
        self.assertEqual(
            json.loads((project / "scenes.json").read_text(encoding="utf-8")),
            {
                "model": "gemini-omni-flash-preview",
                "aspect_ratio": "9:16",
                "characters_file": "stories/flying-auto/characters.json",
                "scenes": [],
            },
        )
        for relative in (
            "assets",
            "videos",
            "reviews",
            "temp/continuity_frames",
            "temp/contact_sheets",
            "output",
        ):
            self.assertTrue((project / relative).is_dir(), relative)

    def test_explicit_slug_supports_non_ascii_title(self) -> None:
        result = create_project(
            self.root,
            title="उड़ता ऑटो",
            slug="udta-auto",
            aspect_ratio="16:9",
        )

        self.assertEqual(result["project"]["slug"], "udta-auto")
        story = self.root / "stories" / "udta-auto" / "story.md"
        self.assertTrue(story.read_text(encoding="utf-8").startswith("# उड़ता ऑटो\n"))

    def test_non_ascii_title_requires_explicit_slug_when_empty(self) -> None:
        with self.assertRaisesRegex(ProjectSetupError, "provide --slug"):
            derive_slug("उड़ता ऑटो")

    def test_invalid_slug_is_rejected_without_creating_project(self) -> None:
        with self.assertRaisesRegex(ProjectSetupError, "Slug must contain"):
            create_project(
                self.root,
                title="Demo",
                slug="../demo",
                aspect_ratio="9:16",
            )

        self.assertFalse((self.root / "stories" / "demo").exists())

    def test_existing_project_is_never_overwritten(self) -> None:
        first = create_project(
            self.root,
            title="Demo",
            aspect_ratio="9:16",
        )
        story = self.root / first["artifacts"]["story"]
        story.write_text("preserve me\n", encoding="utf-8")

        with self.assertRaisesRegex(ProjectSetupError, "already exists"):
            create_project(
                self.root,
                title="Demo",
                aspect_ratio="16:9",
            )

        self.assertEqual(story.read_text(encoding="utf-8"), "preserve me\n")


if __name__ == "__main__":
    unittest.main()

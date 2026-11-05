"""Tests for direct active-video generation and rejected-video archives."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.generate_scenes import archive_active_video, restore_archived_video
from scripts.review_contract import (
    ReviewContractError,
    active_contact_sheet_path,
    archived_path,
    begin_active_review,
    review_path,
    validate_canonical_binding,
    validate_review,
)


class ActiveVideoWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.story = self.root / "stories" / "demo"
        self.config = self.story / "scenes.json"
        self.active = self.story / "videos" / "s001.mp4"
        self.scene = {
            "id": "s001",
            "output_path": "stories/demo/videos/s001.mp4",
        }
        self.config.parent.mkdir(parents=True)
        self.config.write_text(
            json.dumps({"scenes": [self.scene]}), encoding="utf-8"
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def generate_active(
        self,
        contents: bytes,
        history: list[dict[str, object]] | None = None,
    ) -> None:
        self.active.parent.mkdir(parents=True, exist_ok=True)
        self.active.write_bytes(contents)
        begin_active_review(
            self.config, "s001", self.active, self.root, history or []
        )

    def complete_review(self, decision: str) -> dict[str, object]:
        path = review_path(self.config, "s001")
        review = json.loads(path.read_text(encoding="utf-8"))
        sheet = active_contact_sheet_path(self.config, "s001")
        sheet.parent.mkdir(parents=True, exist_ok=True)
        sheet.write_bytes(b"sheet")
        review.update(
            {
                "decision": decision,
                "contact_sheet_path": str(sheet.relative_to(self.root)),
                "media_valid": True,
                "findings": [],
                "next_action": "continue" if decision != "needs_fix" else "retry",
            }
        )
        path.write_text(json.dumps(review), encoding="utf-8")
        return review

    def test_accepted_first_video_is_already_active(self) -> None:
        self.generate_active(b"accepted")
        self.complete_review("accepted")

        review, reviewed = validate_review(self.config, "s001", self.root)

        self.assertEqual(reviewed.resolve(), self.active.resolve())
        self.assertEqual(self.active.read_bytes(), b"accepted")
        validate_canonical_binding(review, self.active, self.root)

    def test_first_failure_is_archived_before_replacement(self) -> None:
        self.generate_active(b"first")
        self.complete_review("needs_fix")

        number, archive, history = archive_active_video(
            self.config, self.scene, self.root
        )

        self.assertEqual(number, 1)
        self.assertFalse(self.active.exists())
        self.assertEqual(archive.read_bytes(), b"first")
        self.assertTrue(
            archived_path(active_contact_sheet_path(self.config, "s001"), 1).is_file()
        )
        self.assertEqual(history[0]["decision"], "needs_fix")
        state = json.loads(review_path(self.config, "s001").read_text())
        self.assertEqual(state["decision"], "pending_generation")

    def test_second_failure_archives_both_and_waits_for_user(self) -> None:
        self.generate_active(b"first")
        self.complete_review("needs_fix")
        _, _, history = archive_active_video(self.config, self.scene, self.root)
        self.generate_active(b"second", history)
        self.complete_review("needs_fix")

        number, archive, history = archive_active_video(
            self.config, self.scene, self.root
        )

        self.assertEqual(number, 2)
        self.assertFalse(self.active.exists())
        self.assertEqual(archive.read_bytes(), b"second")
        self.assertEqual(len(history), 2)
        state = json.loads(review_path(self.config, "s001").read_text())
        self.assertEqual(state["decision"], "await_user")
        self.assertEqual(state["next_action"], "await_user")

    def test_restore_copies_archive_to_active_for_fresh_review(self) -> None:
        self.generate_active(b"first")
        self.complete_review("needs_fix")
        _, first_archive, history = archive_active_video(
            self.config, self.scene, self.root
        )
        self.generate_active(b"second", history)
        self.complete_review("needs_fix")
        archive_active_video(self.config, self.scene, self.root)

        source, active = restore_archived_video(
            self.config, self.scene, 1, self.root
        )

        self.assertEqual(source, first_archive)
        self.assertEqual(active.read_bytes(), b"first")
        state = json.loads(review_path(self.config, "s001").read_text())
        self.assertEqual(state["decision"], "pending_review")
        self.assertEqual(len(state["history"]), 2)

    def test_changed_active_video_cannot_pass_review(self) -> None:
        self.generate_active(b"reviewed")
        self.complete_review("accepted")
        self.active.write_bytes(b"changed")

        with self.assertRaisesRegex(ReviewContractError, "changed after"):
            validate_review(self.config, "s001", self.root)


if __name__ == "__main__":
    unittest.main()

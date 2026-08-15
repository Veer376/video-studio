from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.render_video import RenderError, validate_scene_review


class ReviewGateTests(unittest.TestCase):
    def write_review(self, story: Path, review: dict[str, object]) -> Path:
        review["scene_id"] = "s001"
        attempts = review.get("attempts", [])
        for item in attempts:
            number = item["attempt"]
            candidate = story / "temp" / "partial" / f"s001-attempt-{number}.mp4"
            sheet = story / "temp" / "contact_sheets" / f"s001-attempt-{number}.png"
            candidate.parent.mkdir(parents=True, exist_ok=True)
            sheet.parent.mkdir(parents=True, exist_ok=True)
            candidate.write_bytes(f"attempt {number}".encode())
            sheet.write_bytes(b"sheet")
            item["candidate_path"] = str(candidate)
            item["contact_sheet_path"] = str(sheet)
            item["findings"] = [f"Attempt {number} review finding."]
        review_path = story / "reviews" / "s001.json"
        review_path.parent.mkdir()
        review_path.write_text(json.dumps(review))
        return story / "scenes.json"

    def test_accepts_autonomous_best_available(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            config = self.write_review(Path(temporary_directory), {
                "decision": "best_available",
                "execution_mode": "autonomous",
                "selected_attempt": 2,
                "attempts": [
                    {"attempt": 1, "media_valid": True, "decision": "needs_fix"},
                    {"attempt": 2, "media_valid": True, "decision": "needs_fix"},
                    {"attempt": 3, "media_valid": True, "decision": "needs_fix"},
                ],
                "selection_reason": "Attempt 2 preserves the required ending.",
                "unresolved_findings": ["Minor prop drift remains."],
            })

            review = validate_scene_review(config, "s001")

            self.assertEqual(review["decision"], "best_available")

    def test_rejects_interactive_best_available(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            config = self.write_review(Path(temporary_directory), {
                "decision": "best_available",
                "execution_mode": "interactive",
                "selected_attempt": 2,
                "attempts": [
                    {"attempt": 1, "media_valid": True, "decision": "needs_fix"},
                    {"attempt": 2, "media_valid": True, "decision": "needs_fix"},
                    {"attempt": 3, "media_valid": True, "decision": "needs_fix"},
                ],
                "selection_reason": "Attempt 2 preserves the required ending.",
                "unresolved_findings": ["Minor prop drift remains."],
            })

            with self.assertRaisesRegex(RenderError, "autonomous mode"):
                validate_scene_review(config, "s001")

    def test_rejects_needs_fix(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            config = self.write_review(Path(temporary_directory), {
                "decision": "needs_fix",
                "execution_mode": "interactive",
                "selected_attempt": None,
                "attempts": [],
            })

            with self.assertRaisesRegex(RenderError, "not promotable"):
                validate_scene_review(config, "s001")


if __name__ == "__main__":
    unittest.main()

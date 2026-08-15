from __future__ import annotations

import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from scripts.generate_scenes import (
    ConfigError,
    compile_scene,
    promote_attempt,
    run,
    scene_attempt_path,
    scene_first_frame_path,
    scene_output_path,
    validate_promotion_review,
)
from scripts.review_contract import ReviewContractError, validate_canonical_binding


class CompileSceneTests(unittest.TestCase):
    def test_character_inputs_follow_first_prompt_appearance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            aloo = root / "aloo.jpeg"
            gajar = root / "gajar.jpeg"
            aloo.write_bytes(b"aloo")
            gajar.write_bytes(b"gajar")
            characters = {
                "@aloo": {"resolved_reference_path": aloo},
                "@gajar": {"resolved_reference_path": gajar},
            }
            scene = {
                "id": "s001",
                "prompt": "@gajar pulls the children back while @aloo grabs the rope.",
                "subjects": ["@aloo", "@gajar"],
                "reference_images": [],
            }

            compiled = compile_scene(scene, characters, root)

            self.assertEqual(compiled.handle_order, ["@gajar", "@aloo"])
            self.assertEqual(compiled.images, [gajar, aloo])
            self.assertIn("[# References <IMAGE_REF_0>@Image1]", compiled.prompt)
            self.assertIn("[# References <IMAGE_REF_1>@Image2]", compiled.prompt)
            self.assertIn(
                "<IMAGE_REF_0> pulls the children back while <IMAGE_REF_1> grabs",
                compiled.prompt,
            )
            self.assertEqual(compiled.task, "reference_to_video")

    def test_first_frame_precedes_character_references(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            frame = root / "last_frame.png"
            aloo = root / "aloo.jpeg"
            frame.write_bytes(b"frame")
            aloo.write_bytes(b"aloo")
            characters = {"@aloo": {"resolved_reference_path": aloo}}
            scene = {
                "id": "s002",
                "prompt": "@aloo immediately lunges toward the rope.",
                "subjects": ["@aloo"],
                "reference_images": [],
            }

            compiled = compile_scene(scene, characters, root, first_frame=frame)

            self.assertEqual(compiled.images, [frame, aloo])
            self.assertIn("[# Sources <FIRST_FRAME>@Image1]", compiled.prompt)
            self.assertIn("[# References <IMAGE_REF_0>@Image2]", compiled.prompt)
            self.assertIn("<FIRST_FRAME>", compiled.prompt)
            self.assertEqual(compiled.task, "reference_to_video")

    def test_first_frame_only_uses_image_to_video(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            frame = root / "first-frame.png"
            frame.write_bytes(b"frame")
            scene = {
                "id": "s001",
                "prompt": "Animate <FIRST_FRAME> as one continuous joyful flight.",
                "subjects": [],
                "reference_images": [],
            }

            compiled = compile_scene(scene, {}, root, first_frame=frame)

            self.assertEqual(compiled.images, [frame])
            self.assertEqual(compiled.task, "image_to_video")


class SceneOutputTests(unittest.TestCase):
    def test_output_path_resolves_from_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            scene = {"id": "s001", "output_path": "scenes/s001.mp4"}

            output = scene_output_path(scene, root)

            self.assertEqual(output, root / "scenes" / "s001.mp4")

    def test_curated_first_frame_resolves_from_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            frame = root / "assets" / "continuity" / "s014.png"
            frame.parent.mkdir(parents=True)
            frame.write_bytes(b"frame")
            scene = {
                "id": "s014",
                "first_frame_path": "assets/continuity/s014.png",
            }

            output = scene_first_frame_path(scene, root)

            self.assertEqual(output, frame)

    def test_attempt_path_is_story_local_and_numbered(self) -> None:
        config = Path("/project/stories/demo/scenes.json")

        output = scene_attempt_path(config, "s007", 2)

        self.assertEqual(
            output,
            Path("/project/stories/demo/temp/partial/s007-attempt-2.mp4"),
        )

    def test_attempt_four_is_rejected(self) -> None:
        with self.assertRaisesRegex(ConfigError, "between 1 and 3"):
            scene_attempt_path(Path("/project/stories/demo/scenes.json"), "s001", 4)

    def test_best_available_requires_autonomous_review(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            story = Path(temporary_directory)
            config = story / "scenes.json"
            attempts = []
            for number in range(1, 4):
                candidate = scene_attempt_path(config, "s001", number)
                sheet = story / "temp" / "contact_sheets" / f"s001-attempt-{number}.png"
                candidate.parent.mkdir(parents=True, exist_ok=True)
                sheet.parent.mkdir(parents=True, exist_ok=True)
                candidate.write_bytes(f"attempt {number}".encode())
                sheet.write_bytes(b"sheet")
                attempts.append({
                    "attempt": number,
                    "candidate_path": str(candidate),
                    "contact_sheet_path": str(sheet),
                    "media_valid": True,
                    "decision": "needs_fix",
                    "findings": [f"Attempt {number} has a visible defect."],
                })
            review_path = story / "reviews" / "s001.json"
            review_path.parent.mkdir()
            review_path.write_text(json.dumps({
                "scene_id": "s001",
                "decision": "best_available",
                "execution_mode": "interactive",
                "selected_attempt": 2,
                "attempts": attempts,
                "selection_reason": "Attempt 2 preserves the required ending.",
                "unresolved_findings": ["Minor prop drift remains."],
            }))

            with self.assertRaisesRegex(ConfigError, "autonomous mode"):
                validate_promotion_review(config, "s001", 2)

    def test_promote_attempt_copies_only_reviewed_selection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            config = root / "stories" / "demo" / "scenes.json"
            first_candidate = scene_attempt_path(config, "s001", 1)
            candidate = scene_attempt_path(config, "s001", 2)
            candidate.parent.mkdir(parents=True)
            first_candidate.write_bytes(b"first attempt")
            candidate.write_bytes(b"selected attempt")
            first_sheet = (
                config.parent / "temp" / "contact_sheets" / "s001-attempt-1.png"
            )
            sheet = config.parent / "temp" / "contact_sheets" / "s001-attempt-2.png"
            sheet.parent.mkdir(parents=True)
            first_sheet.write_bytes(b"sheet")
            sheet.write_bytes(b"sheet")
            review_path = config.parent / "reviews" / "s001.json"
            review_path.parent.mkdir()
            review_path.write_text(json.dumps({
                "scene_id": "s001",
                "decision": "accepted_with_note",
                "execution_mode": "interactive",
                "selected_attempt": 2,
                "attempts": [
                    {
                        "attempt": 1,
                        "candidate_path": str(first_candidate),
                        "contact_sheet_path": str(first_sheet),
                        "media_valid": True,
                        "decision": "needs_fix",
                        "findings": ["The required action is missing."],
                    },
                    {
                        "attempt": 2,
                        "candidate_path": str(candidate),
                        "contact_sheet_path": str(sheet),
                        "media_valid": True,
                        "decision": "accepted_with_note",
                        "findings": ["A harmless variation remains."],
                    },
                ],
            }))
            scene = {
                "id": "s001",
                "output_path": "stories/demo/videos/s001.mp4",
            }

            with patch("scripts.generate_scenes.verify_video"):
                source, destination = promote_attempt(config, scene, 2, root)

            self.assertEqual(source, candidate)
            self.assertEqual(destination.read_bytes(), b"selected attempt")
            self.assertTrue(candidate.is_file())
            persisted_review = json.loads(review_path.read_text())
            self.assertEqual(persisted_review["promoted_attempt"], 2)
            self.assertEqual(len(persisted_review["canonical_sha256"]), 64)
            validate_canonical_binding(persisted_review, destination, root)

            destination.write_bytes(b"tampered canonical")
            with self.assertRaisesRegex(
                ReviewContractError, "does not match the promoted attempt"
            ):
                validate_canonical_binding(persisted_review, destination, root)

    def test_generation_writes_attempt_without_creating_canonical(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            story = root / "stories" / "demo"
            story.mkdir(parents=True)
            characters = story / "characters.json"
            characters.write_text(json.dumps({"characters": []}))
            canonical = root / "canonical" / "s001.mp4"
            config = story / "scenes.json"
            config.write_text(json.dumps({
                "characters_file": str(characters),
                "scenes": [{
                    "id": "s001",
                    "part_id": "part_01",
                    "prompt": "A quiet landscape with no recurring subjects.",
                    "subjects": [],
                    "reference_images": [],
                    "reference_scene_id": None,
                    "output_path": str(canonical),
                }],
            }))
            args = Namespace(
                config=config,
                scene=["s001"],
                part=[],
                dry_run=False,
                regenerate=False,
                attempt=1,
                promote_attempt=None,
                backend="auto",
                gcp_project=None,
            )

            def fake_generate_video(**kwargs: object) -> int:
                Path(kwargs["output"]).write_bytes(b"candidate")
                return len(b"candidate")

            with (
                patch(
                    "scripts.generate_scenes.create_client",
                    return_value=(object(), "test"),
                ),
                patch(
                    "scripts.generate_scenes.generate_video",
                    side_effect=fake_generate_video,
                ),
                patch("scripts.generate_scenes.verify_video"),
            ):
                result = run(args)

            candidate = scene_attempt_path(config, "s001", 1)
            self.assertEqual(result, 0)
            self.assertEqual(candidate.read_bytes(), b"candidate")
            self.assertFalse(canonical.exists())

    def test_regeneration_never_overwrites_existing_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            story = root / "stories" / "demo"
            story.mkdir(parents=True)
            characters = story / "characters.json"
            characters.write_text(json.dumps({"characters": []}))
            config = story / "scenes.json"
            config.write_text(json.dumps({
                "characters_file": str(characters),
                "scenes": [{
                    "id": "s001",
                    "part_id": "part_01",
                    "prompt": "A quiet landscape.",
                    "subjects": [],
                    "reference_images": [],
                    "reference_scene_id": None,
                    "output_path": str(root / "canonical" / "s001.mp4"),
                }],
            }))
            candidate = scene_attempt_path(config, "s001", 1)
            candidate.parent.mkdir(parents=True)
            candidate.write_bytes(b"preserve me")
            args = Namespace(
                config=config,
                scene=["s001"],
                part=[],
                dry_run=False,
                regenerate=True,
                attempt=1,
                promote_attempt=None,
                backend="auto",
                gcp_project=None,
            )

            with self.assertRaisesRegex(ConfigError, "immutable"):
                run(args)

            self.assertEqual(candidate.read_bytes(), b"preserve me")

    def test_dependent_scene_rejects_unbound_predecessor_canonical(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            story = root / "stories" / "demo"
            story.mkdir(parents=True)
            characters = story / "characters.json"
            characters.write_text(json.dumps({"characters": []}))
            predecessor = root / "canonical" / "s001.mp4"
            predecessor.parent.mkdir()
            predecessor.write_bytes(b"unbound canonical")
            config = story / "scenes.json"
            config.write_text(json.dumps({
                "characters_file": str(characters),
                "scenes": [
                    {
                        "id": "s001",
                        "part_id": "part_01",
                        "prompt": "Opening landscape.",
                        "subjects": [],
                        "reference_images": [],
                        "reference_scene_id": None,
                        "output_path": str(predecessor),
                    },
                    {
                        "id": "s002",
                        "part_id": "part_01",
                        "prompt": "Continue from <FIRST_FRAME>.",
                        "subjects": [],
                        "reference_images": [],
                        "reference_scene_id": "s001",
                        "output_path": str(root / "canonical" / "s002.mp4"),
                    },
                ],
            }))
            candidate = scene_attempt_path(config, "s001", 1)
            sheet = story / "temp" / "contact_sheets" / "s001-attempt-1.png"
            candidate.parent.mkdir(parents=True)
            sheet.parent.mkdir(parents=True)
            candidate.write_bytes(b"reviewed candidate")
            sheet.write_bytes(b"sheet")
            review_path = story / "reviews" / "s001.json"
            review_path.parent.mkdir()
            review_path.write_text(json.dumps({
                "scene_id": "s001",
                "decision": "accepted",
                "execution_mode": "interactive",
                "selected_attempt": 1,
                "attempts": [{
                    "attempt": 1,
                    "candidate_path": str(candidate),
                    "contact_sheet_path": str(sheet),
                    "media_valid": True,
                    "decision": "accepted",
                    "findings": ["The opening beat is correct."],
                }],
                "next_action": "continue",
            }))
            args = Namespace(
                config=config,
                scene=["s002"],
                part=[],
                dry_run=True,
                regenerate=False,
                attempt=1,
                promote_attempt=None,
                backend="auto",
                gcp_project=None,
            )

            with self.assertRaisesRegex(ConfigError, "reviewed promoted canonical"):
                run(args)


if __name__ == "__main__":
    unittest.main()

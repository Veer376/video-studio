"""Regression tests for project-scene compilation and the Flow request adapter."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import generate_scenes
from scripts.video.base import CharacterEntry, VideoError, compile_scene
from scripts.video.flow import (
    FlowProvider,
    prepare_scene_input,
    requires_google_fallback,
)


class FlowPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.aloo_image = self.root / "aloo.png"
        self.gajar_image = self.root / "gajar.png"
        self.first_frame = self.root / "first.png"
        for path in (self.aloo_image, self.gajar_image, self.first_frame):
            path.write_bytes(b"test-image")

        self.characters = {
            "@aloo": CharacterEntry(
                handle="@aloo",
                name="Aloo",
                reference_path=str(self.aloo_image),
                resolved_reference_path=self.aloo_image,
                profile="round potato face, yellow kurta",
            ),
            "@gajar": CharacterEntry(
                handle="@gajar",
                name="Gajar",
                reference_path=str(self.gajar_image),
                resolved_reference_path=self.gajar_image,
                profile="carrot face, orange kurta",
            ),
        }
        self.scene = {
            "id": "s001",
            "prompt": "@aloo runs beside @gajar. No scene cuts.",
            "subjects": ["@aloo", "@gajar"],
            "reference_images": [],
        }

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_story_runner_uses_the_shared_compiler(self) -> None:
        self.assertIs(generate_scenes.compile_scene, compile_scene)

    def test_flow_reference_mode_preserves_handles_and_binds_image_order(self) -> None:
        compiled = compile_scene(self.scene, self.characters, self.root)
        request = prepare_scene_input(compiled, None)

        self.assertEqual(request.images, (self.aloo_image, self.gajar_image))
        self.assertIsNone(request.start_frame)
        self.assertIn("Reference image 1 depicts @aloo", request.prompt)
        self.assertIn("Reference image 2 depicts @gajar", request.prompt)
        self.assertIn("@aloo (round potato face, yellow kurta)", request.prompt)
        self.assertNotIn("<IMAGE_REF_0>", request.prompt)

    def test_flow_start_plus_references_requires_google_fallback(self) -> None:
        compiled = compile_scene(
            self.scene, self.characters, self.root, first_frame=self.first_frame
        )

        self.assertTrue(requires_google_fallback(compiled, self.first_frame))
        with self.assertRaisesRegex(VideoError, "route this scene through Google"):
            prepare_scene_input(compiled, self.first_frame)

    def test_flow_start_only_mode_remains_supported(self) -> None:
        scene = {
            "id": "s002",
            "prompt": "The supplied landscape begins moving. No scene cuts.",
            "subjects": [],
            "reference_images": [],
        }
        compiled = compile_scene(
            scene, self.characters, self.root, first_frame=self.first_frame
        )
        request = prepare_scene_input(compiled, self.first_frame)

        self.assertFalse(requires_google_fallback(compiled, self.first_frame))
        self.assertEqual(request.images, ())
        self.assertEqual(request.start_frame, self.first_frame)
        self.assertTrue(request.prompt.startswith("Use the supplied start image"))

    def test_prefixed_handles_compile_as_exact_tokens(self) -> None:
        alternate_image = self.root / "aloo-alt.png"
        alternate_image.write_bytes(b"test-image")
        characters = {
            **self.characters,
            "@aloo-alt": CharacterEntry(
                handle="@aloo-alt",
                name="Aloo Alt",
                reference_path=str(alternate_image),
                resolved_reference_path=alternate_image,
                profile="alternate costume",
            ),
        }
        scene = {
            "id": "prefix",
            "prompt": "@aloo-alt follows @aloo.",
            "subjects": ["@aloo", "@aloo-alt"],
            "reference_images": [],
        }

        compiled = compile_scene(scene, characters, self.root)

        self.assertEqual(compiled.handle_order, ["@aloo-alt", "@aloo"])
        self.assertTrue(compiled.prompt.rstrip().endswith("<IMAGE_REF_0> follows <IMAGE_REF_1>."))

    def test_provider_sends_ordered_reference_media_ids(self) -> None:
        provider = FlowProvider()
        output = self.root / "result.mp4"
        posted: list[dict[str, object]] = []

        def fake_post(url: str, body: dict[str, object], **_: object) -> dict[str, object]:
            posted.append(body)
            return {"job_id": "job-1", "status": "succeeded", "data": [{}]}

        with (
            patch.object(provider, "preflight", return_value=True),
            patch.object(provider, "check_credits", return_value=True),
            patch("scripts.video.flow.upload_media_file", side_effect=[("media-a", False), ("media-b", False)]),
            patch("scripts.video.flow._post", side_effect=fake_post),
            patch.object(provider, "_download_output", return_value=123),
        ):
            result = provider.generate_video(
                prompt="REFERENCE IMAGE BINDINGS:\n- Reference image 1 depicts @aloo.",
                output=output,
                images=(self.aloo_image, self.gajar_image),
                duration=10,
            )

        self.assertEqual(result, 123)
        self.assertEqual(posted[0]["ref_media_ids"], ["media-a", "media-b"])
        self.assertNotIn("start_media_id", posted[0])

    def test_provider_sends_start_frame_separately(self) -> None:
        provider = FlowProvider()
        posted: list[dict[str, object]] = []

        with (
            patch.object(provider, "preflight", return_value=True),
            patch.object(provider, "check_credits", return_value=True),
            patch("scripts.video.flow.upload_media_file", return_value=("start-1", False)),
            patch(
                "scripts.video.flow._post",
                side_effect=lambda _url, body, **_kwargs: (
                    posted.append(body)
                    or {"job_id": "job-2", "status": "succeeded", "data": [{}]}
                ),
            ),
            patch.object(provider, "_download_output", return_value=321),
        ):
            provider.generate_video(
                prompt="Animate this exact opening frame.",
                output=self.root / "result.mp4",
                start_frame=self.first_frame,
                duration=8,
            )

        self.assertEqual(posted[0]["start_media_id"], "start-1")
        self.assertNotIn("ref_media_ids", posted[0])

    def test_provider_honors_legacy_image_to_video_task(self) -> None:
        provider = FlowProvider()
        posted: list[dict[str, object]] = []

        with (
            patch.object(provider, "preflight", return_value=True),
            patch.object(provider, "check_credits", return_value=True),
            patch("scripts.video.flow.upload_media_file", return_value=("start-legacy", False)),
            patch(
                "scripts.video.flow._post",
                side_effect=lambda _url, body, **_kwargs: (
                    posted.append(body)
                    or {"job_id": "job-3", "status": "succeeded", "data": [{}]}
                ),
            ),
            patch.object(provider, "_download_output", return_value=111),
        ):
            provider.generate_video(
                prompt="Animate this frame.",
                output=self.root / "result.mp4",
                images=(self.first_frame,),
                task="image_to_video",
                duration=6,
            )

        self.assertEqual(posted[0]["start_media_id"], "start-legacy")
        self.assertNotIn("ref_media_ids", posted[0])

    def test_provider_rejects_ambiguous_start_plus_references(self) -> None:
        provider = FlowProvider()
        with self.assertRaisesRegex(VideoError, "cannot combine"):
            provider.generate_video(
                prompt="Animate.",
                output=self.root / "result.mp4",
                images=(self.aloo_image,),
                start_frame=self.first_frame,
            )

    def test_provider_rejects_unsupported_duration_before_network_use(self) -> None:
        provider = FlowProvider()
        with self.assertRaisesRegex(VideoError, "4, 6, 8, 10"):
            provider.generate_video(
                prompt="Animate.",
                output=self.root / "result.mp4",
                duration=7,
            )


if __name__ == "__main__":
    unittest.main()

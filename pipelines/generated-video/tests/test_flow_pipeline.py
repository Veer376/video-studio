"""Regression tests for project-scene compilation and the Flow request adapter."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import generate_scenes
from scripts.video.base import (
    CharacterEntry,
    ConfigError,
    CreditError,
    LocationEntry,
    VideoError,
    compile_scene,
)
from scripts.video.flow import (
    FlowProvider,
    flow_output_paths,
    prepare_scene_input,
    resolve_omni_model_key,
    requires_google_fallback,
)


class FlowPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.aloo_image = self.root / "aloo.png"
        self.gajar_image = self.root / "gajar.png"
        self.first_frame = self.root / "first.png"
        self.water_point_image = self.root / "water-point.png"
        for path in (
            self.aloo_image,
            self.gajar_image,
            self.first_frame,
            self.water_point_image,
        ):
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
        self.locations = {
            "@location-water-point": LocationEntry(
                handle="@location-water-point",
                name="Water Point",
                reference_path=str(self.water_point_image),
                resolved_reference_path=self.water_point_image,
                profile="old public well beside cracked village earth",
            )
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
        self.assertIn("- @aloo (Aloo):", request.prompt)
        self.assertIn("round potato face, yellow kurta", request.prompt)
        self.assertEqual(request.prompt.count("round potato face, yellow kurta"), 1)
        self.assertIn("@aloo runs beside @gajar. No scene cuts.", request.prompt)
        self.assertNotIn("<IMAGE_REF_0>", request.prompt)

    def test_flow_defines_repeated_character_profile_only_once(self) -> None:
        scene = {
            "id": "repeated-profile",
            "prompt": (
                "@aloo enters. Only @aloo speaks. @aloo says exactly: \"hello\". "
                "End with @aloo still in frame."
            ),
            "subjects": ["@aloo"],
            "reference_images": [],
        }

        compiled = compile_scene(scene, self.characters, self.root)
        request = prepare_scene_input(compiled, None)

        self.assertEqual(request.prompt.count("round potato face, yellow kurta"), 1)
        self.assertEqual(request.prompt.count("@aloo"), 6)
        self.assertIn(
            "@aloo enters. Only @aloo speaks. @aloo says exactly: \"hello\".",
            request.prompt,
        )
        self.assertEqual(compiled.prompt.count("round potato face, yellow kurta"), 1)

    def test_flow_start_plus_references_requires_google_fallback(self) -> None:
        compiled = compile_scene(
            self.scene, self.characters, self.root, first_frame=self.first_frame
        )

        self.assertIn("Use Image1 as the literal starting frame at time 0", compiled.prompt)
        self.assertIn("Use every other supplied image only as identity/environment reference", compiled.prompt)
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
        self.assertIn("- <IMAGE_REF_0> (@aloo-alt, Aloo Alt):", compiled.prompt)
        self.assertIn("- <IMAGE_REF_1> (@aloo, Aloo):", compiled.prompt)

    def test_narration_handle_is_audio_only_and_does_not_bind_an_image(self) -> None:
        (self.root / "voices.json").write_text(
            '{"voices":[{"handle":"@narration-kathamind","profile":"deep stable narrator"}]}',
            encoding="utf-8",
        )
        scene = {
            "id": "narration",
            "prompt": (
                'A single off-screen @narration-kathamind voiceover says exactly: '
                '"कलयुग का अंधकार फैल चुका था...". No character dialogue.'
            ),
            "subjects": [],
            "reference_images": [],
        }

        compiled = compile_scene(scene, self.characters, self.root)

        self.assertEqual(compiled.images, [])
        self.assertEqual(compiled.handle_order, [])
        self.assertIn("NARRATION VOICE PROFILES:", compiled.prompt)
        self.assertIn("@narration-kathamind: deep stable narrator", compiled.prompt)
        self.assertIn("off-screen @narration-kathamind voiceover", compiled.prompt)
        self.assertEqual(compiled.task, "text_to_video")

    def test_character_and_narration_handles_compile_independently(self) -> None:
        (self.root / "voices.json").write_text(
            '{"voices":[{"handle":"@narration-kathamind","profile":"deep stable narrator"}]}',
            encoding="utf-8",
        )
        scene = {
            "id": "mixed",
            "prompt": (
                '@aloo looks toward the horizon. A single off-screen '
                '@narration-kathamind voiceover says exactly: "समय बदल चुका था।"'
            ),
            "subjects": ["@aloo"],
            "reference_images": [],
        }

        compiled = compile_scene(scene, self.characters, self.root)

        self.assertEqual(compiled.images, [self.aloo_image])
        self.assertEqual(compiled.handle_order, ["@aloo"])
        self.assertIn("<IMAGE_REF_0> looks toward the horizon", compiled.prompt)
        self.assertIn("- <IMAGE_REF_0> (@aloo, Aloo):", compiled.prompt)
        self.assertIn("@narration-kathamind voiceover", compiled.prompt)

        flow_request = prepare_scene_input(compiled, None)
        self.assertEqual(flow_request.prompt.count("round potato face, yellow kurta"), 1)
        self.assertEqual(flow_request.prompt.count("deep stable narrator"), 1)
        self.assertIn("@aloo looks toward the horizon", flow_request.prompt)
        self.assertIn("@narration-kathamind voiceover", flow_request.prompt)

    def test_unknown_narration_handle_is_rejected(self) -> None:
        scene = {
            "id": "unknown-narrator",
            "prompt": "A single off-screen @narration-missing voiceover says exactly: \"hello\".",
            "subjects": [],
            "reference_images": [],
        }

        with self.assertRaisesRegex(ConfigError, "unknown narration handles"):
            compile_scene(scene, self.characters, self.root)


    def test_location_handle_binds_visual_reference_without_becoming_subject(self) -> None:
        scene = {
            "id": "location",
            "prompt": "@aloo waits at @location-water-point.",
            "subjects": ["@aloo"],
            "locations": ["@location-water-point"],
            "reference_images": [],
        }

        compiled = compile_scene(
            scene, self.characters, self.root, locations=self.locations
        )
        request = prepare_scene_input(compiled, None)

        self.assertEqual(
            compiled.images, [self.aloo_image, self.water_point_image]
        )
        self.assertEqual(
            compiled.handle_order, ["@aloo", "@location-water-point"]
        )
        self.assertIn("LOCATION REFERENCE BINDINGS", compiled.prompt)
        self.assertNotIn("Water Point", compiled.prompt)
        self.assertNotIn("old public well beside cracked village earth", compiled.prompt)
        self.assertIn("Reference image 2 depicts @location-water-point", request.prompt)

    def test_location_prompt_handle_requires_scene_location_declaration(self) -> None:
        scene = {
            "id": "missing-location-declaration",
            "prompt": "@aloo waits at @location-water-point.",
            "subjects": ["@aloo"],
            "locations": [],
            "reference_images": [],
        }

        with self.assertRaisesRegex(
            ConfigError, "prompt location handles absent from locations"
        ):
            compile_scene(scene, self.characters, self.root, locations=self.locations)

    def test_unknown_location_handle_is_rejected(self) -> None:
        scene = {
            "id": "unknown-location",
            "prompt": "@aloo waits at @location-missing.",
            "subjects": ["@aloo"],
            "locations": ["@location-missing"],
            "reference_images": [],
        }

        with self.assertRaisesRegex(ConfigError, "unknown location handles"):
            compile_scene(scene, self.characters, self.root, locations=self.locations)

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
        with self.assertRaisesRegex(VideoError, "cannot combine a literal start frame"):
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

    def test_omni_model_resolver_is_operation_and_resolution_aware(self) -> None:
        self.assertEqual(
            resolve_omni_model_key(
                operation="t2v", duration=8, resolution="720p", model="omni"
            ),
            "abra_t2v_8s",
        )
        self.assertEqual(
            resolve_omni_model_key(
                operation="r2v", duration=10, resolution="360p", model="omni"
            ),
            "abra_r2v_10s_360p",
        )
        self.assertEqual(
            resolve_omni_model_key(
                operation="first_last", duration=6, resolution="720p", model="omni"
            ),
            "omni_flash_i2v_6s_first_last",
        )
        self.assertEqual(
            resolve_omni_model_key(
                operation="edit", duration=4, resolution="360p", model="omni"
            ),
            "abra_edit_360p",
        )

    def test_provider_sends_count_seed_resolution_model_and_idempotency(self) -> None:
        provider = FlowProvider()
        posted: list[tuple[dict[str, object], dict[str, str]]] = []

        def fake_post(_url, body, headers=None, **_kwargs):
            posted.append((body, headers or {}))
            return {
                "job_id": "job-count",
                "status": "succeeded",
                "data": [{}, {}],
            }

        with (
            patch.object(provider, "preflight", return_value=True),
            patch.object(provider, "check_credits", return_value=True),
            patch("scripts.video.flow._post", side_effect=fake_post),
            patch.object(provider, "_download_output", return_value=222) as download,
        ):
            result = provider.generate_video(
                prompt="Two variants.",
                output=self.root / "result.mp4",
                duration=8,
                resolution="360p",
                seed=12345,
                count=2,
                idempotency_key="stable-key",
            )

        self.assertEqual(result, 222)
        self.assertEqual(posted[0][0]["n"], 2)
        self.assertEqual(posted[0][0]["seed"], 12345)
        self.assertEqual(posted[0][0]["video_model"], "abra_t2v_8s_360p")
        self.assertEqual(posted[0][1]["Idempotency-Key"], "stable-key")
        download.assert_called_once_with(
            [{}, {}], self.root / "result.mp4", expected_count=2
        )

    def test_flow_output_paths_suffix_multiple_outputs(self) -> None:
        output = self.root / "shot.mp4"
        self.assertEqual(
            flow_output_paths(output, 2),
            (self.root / "shot-01.mp4", self.root / "shot-02.mp4"),
        )
        self.assertEqual(flow_output_paths(output, 1), (output,))

    def test_edit_credit_check_uses_edit_cost(self) -> None:
        provider = FlowProvider()
        with patch("scripts.video.flow._get", return_value={"total_credits": 39}):
            with self.assertRaises(CreditError):
                provider.check_credits(
                    duration=8,
                    count=1,
                    resolution="720p",
                    operation="edit",
                )
        with patch("scripts.video.flow._get", return_value={"total_credits": 40}):
            self.assertTrue(
                provider.check_credits(
                    duration=8,
                    count=1,
                    resolution="720p",
                    operation="edit",
                )
            )


if __name__ == "__main__":
    unittest.main()

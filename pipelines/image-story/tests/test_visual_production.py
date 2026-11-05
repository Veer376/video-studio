from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from scripts.production.anchors import AnchorRegistry
from scripts.production.io_utils import ProjectLock
from scripts.production.manifest import ManifestStore
from scripts.production.planner import PlanError, build_plan
from scripts.production.providers import (
    FlowImageProvider,
    FlowMediaCache,
    FlowVideoProvider,
    PreparedFlowVideo,
    ProviderNoResultRejection,
    VideoPoll,
    VideoSubmission,
)
from scripts.production.references import ReferenceError, image_references_for_node
from scripts.production.runner import (
    ProductionError,
    ProductionRunner,
    ProductionSettings,
    flow_recovery_idempotency_key,
    select_assets,
)


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def make_project(root: Path) -> Path:
    project = root / "story"
    project.mkdir()
    scenes = {
        "version": 1,
        "scenes": [
            {
                "id": "scene-001",
                "text": "one",
                "image_prompt": "state one",
                "continuation_image_prompts": [],
                "subjects": ["person"],
                "location_id": "room",
                "reference_scene_id": None,
                "asset_strategy": "new_still_candidate",
                "duration": 4.0,
            },
            {
                "id": "scene-002",
                "text": "two",
                "image_prompt": "state two A",
                "continuation_image_prompts": ["state two B"],
                "subjects": ["person"],
                "location_id": "room",
                "reference_scene_id": "scene-001",
                "asset_strategy": "new_still_or_short_video_candidate",
                "duration": 5.5,
            },
            {
                "id": "scene-003",
                "text": "three",
                "image_prompt": "state three",
                "continuation_image_prompts": [],
                "subjects": ["person"],
                "location_id": "room",
                "reference_scene_id": "scene-002",
                "asset_strategy": "continuation_candidate",
                "duration": 4.0,
            },
            {
                "id": "scene-004",
                "text": "four",
                "image_prompt": "state four A",
                "continuation_image_prompts": ["state four B", "state four C"],
                "subjects": ["person"],
                "location_id": "room",
                "reference_scene_id": None,
                "asset_strategy": "three_beat_multi_asset_candidate",
                "duration": 9.0,
            },
        ],
    }
    continuity = {
        "version": 1,
        "subjects": {"person": {"role": "recurring person"}},
        "locations": {"room": {"role": "recurring room"}},
    }
    session = {
        "visual": {
            "aspect_ratio": "16:9",
            "style_id": "3d_digital_realism",
            "style_prompt": "high-end stylized 3D digital illustration",
        }
    }
    write_json(project / "scenes.json", scenes)
    write_json(project / "continuity.json", continuity)
    write_json(project / "session.json", session)
    return project


class FakeImageProvider:
    name = "fake"

    def __init__(self, fail: bool = False) -> None:
        self.calls: list[dict] = []
        self.fail = fail

    def generate(
        self,
        *,
        prompt,
        output,
        references,
        model,
        aspect_ratio,
        idempotency_key=None,
    ) -> None:
        self.calls.append(
            {
                "prompt": prompt,
                "output": output,
                "references": tuple(ref.asset_id for ref in references),
                "model": model,
                "aspect_ratio": aspect_ratio,
                "idempotency_key": idempotency_key,
            }
        )
        if self.fail:
            raise RuntimeError("synthetic provider failure")
        seed = prompt + "|" + "|".join(ref.sha256 for ref in references)
        digest = hashlib.sha256(seed.encode()).digest()
        output.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (8, 8), tuple(digest[:3])).save(output, format="PNG")


class SequencedFlowImageProvider(FakeImageProvider):
    name = "flow"

    def __init__(self, outcomes: list[str]) -> None:
        super().__init__()
        self.outcomes = list(outcomes)

    def generate(self, **kwargs) -> None:
        self.calls.append(
            {
                "prompt": kwargs["prompt"],
                "output": kwargs["output"],
                "references": tuple(ref.asset_id for ref in kwargs["references"]),
                "model": kwargs["model"],
                "aspect_ratio": kwargs["aspect_ratio"],
                "idempotency_key": kwargs.get("idempotency_key"),
            }
        )
        outcome = self.outcomes.pop(0) if self.outcomes else "success"
        if outcome == "high_traffic":
            raise ProviderNoResultRejection(
                "PUBLIC_ERROR_HIGH_TRAFFIC",
                "synthetic high traffic rejection",
            )
        if outcome == "ambiguous":
            raise RuntimeError("synthetic ambiguous transport failure")
        output = kwargs["output"]
        output.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (8, 8), (11, 22, 33)).save(output, format="PNG")


class FakeFlowVideoProvider:
    def __init__(self, *, finish: bool) -> None:
        self.finish = finish
        self.prepare_calls = 0
        self.prepare_checks: list[bool] = []
        self.submit_calls = 0
        self.poll_calls = 0
        self.submit_keys: list[str | None] = []

    def prepare(self, **kwargs) -> PreparedFlowVideo:
        self.prepare_calls += 1
        self.prepare_checks.append(bool(kwargs.get("check_credits", True)))
        body = {
            "prompt": kwargs["prompt"],
            "duration": kwargs["duration"],
            "aspect": "portrait" if kwargs["aspect_ratio"] == "9:16" else "landscape",
            "n": 1,
            "start_media_id": "fake-start",
        }
        if kwargs.get("end_frame") is not None:
            body["end_media_id"] = "fake-end"
        return PreparedFlowVideo(body=body)

    def submit_prepared(self, **kwargs) -> VideoSubmission:
        self.submit_calls += 1
        self.submit_keys.append(kwargs.get("idempotency_key"))
        return VideoSubmission(job_id="job-123", status="queued")

    def poll_once(self, job_id: str) -> VideoPoll:
        self.poll_calls += 1
        if self.finish:
            return VideoPoll(status="succeeded", items=({"fake": True},))
        return VideoPoll(status="queued")

    def download_items(self, items, output: Path) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"fake-video")


class VisualProductionTests(unittest.TestCase):
    def test_planner_uses_terminal_continuation_for_next_scene(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp))
            plan = build_plan(project)
            self.assertEqual(
                plan.node_by_id["scene-003:primary"].dependencies,
                ("scene-002:c01",),
            )

    def test_multi_continuation_chain_is_strictly_sequential(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp))
            plan = build_plan(project)
            self.assertEqual(plan.node_by_id["scene-004:c01"].dependencies, ("scene-004:primary",))
            self.assertEqual(plan.node_by_id["scene-004:c02"].dependencies, ("scene-004:c01",))

    def test_planner_applies_locked_session_style_exactly_once_to_every_asset_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp))
            video_prompts = project / "video-prompts.json"
            write_json(
                video_prompts,
                {
                    "scenes": {
                        "scene-002": {
                            "prompt": "single continuous unbroken shot; subject shifts attention",
                            "start_asset": "primary",
                            "end_asset": "terminal",
                            "duration": 6,
                        }
                    }
                },
            )
            plan = build_plan(project, video_prompts_path=video_prompts)
            style = "high-end stylized 3D digital illustration"
            self.assertEqual(plan.visual_style_id, "3d_digital_realism")
            self.assertEqual(plan.aspect_ratio, "16:9")
            for node in plan.nodes:
                self.assertTrue(node.prompt.startswith(style + " — "), node.asset_id)
                self.assertEqual(node.prompt.count(style), 1, node.asset_id)

    def test_planner_fails_closed_without_approved_session_visual_design(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp))
            (project / "session.json").unlink()
            with self.assertRaisesRegex(ValueError, "approved visual design is missing"):
                build_plan(project)

    def test_planner_rejects_scene_local_competing_rendering_medium(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp))
            scenes = json.loads((project / "scenes.json").read_text(encoding="utf-8"))
            scenes["scenes"][0]["image_prompt"] += " — photorealistic rendering"
            write_json(project / "scenes.json", scenes)
            with self.assertRaisesRegex(ValueError, "rendering medium controlled by session.visual"):
                build_plan(project)

    def test_runner_rejects_aspect_ratio_that_conflicts_with_session_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp))
            plan = build_plan(project)
            with self.assertRaisesRegex(ProductionError, "conflicts with locked"):
                ProductionRunner(
                    plan=plan,
                    manifest=ManifestStore(project / "production-manifest.json", project),
                    anchors=AnchorRegistry(project / "production-anchors.json"),
                    settings=ProductionSettings(aspect_ratio="9:16"),
                    image_provider=FakeImageProvider(),
                )



    def test_exact_rerun_makes_zero_new_image_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp))
            plan = build_plan(project)
            manifest = ManifestStore(project / "production-manifest.json", project)
            anchors = AnchorRegistry(project / "production-anchors.json")
            provider = FakeImageProvider()
            runner = ProductionRunner(
                plan=plan,
                manifest=manifest,
                anchors=anchors,
                settings=ProductionSettings(image_provider="flow", image_model="pro"),
                image_provider=provider,
            )
            selected = select_assets(plan, scene_ids=("scene-001", "scene-002", "scene-003"), phase="images")
            first = runner.run(selected, phase="images")
            first_call_count = len(provider.calls)
            second = runner.run(selected, phase="images")

            self.assertEqual(first_call_count, 4)
            self.assertEqual(len(provider.calls), first_call_count)
            self.assertEqual(len(first.completed), 4)
            self.assertEqual(len(second.skipped), 4)

    def test_changed_parent_prompt_invalidates_visual_descendants(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp))
            manifest = ManifestStore(project / "production-manifest.json", project)
            anchors = AnchorRegistry(project / "production-anchors.json")
            provider = FakeImageProvider()
            plan = build_plan(project)
            selected = select_assets(plan, scene_ids=("scene-001", "scene-002", "scene-003"), phase="images")
            ProductionRunner(
                plan=plan,
                manifest=manifest,
                anchors=anchors,
                settings=ProductionSettings(image_provider="google"),
                image_provider=provider,
            ).run(selected, phase="images")
            original_calls = len(provider.calls)

            source = json.loads((project / "scenes.json").read_text())
            source["scenes"][0]["image_prompt"] = "state one CHANGED"
            write_json(project / "scenes.json", source)
            changed_plan = build_plan(project)
            changed_selected = select_assets(
                changed_plan,
                scene_ids=("scene-001", "scene-002", "scene-003"),
                phase="images",
            )
            ProductionRunner(
                plan=changed_plan,
                manifest=manifest,
                anchors=anchors,
                settings=ProductionSettings(image_provider="google"),
                image_provider=provider,
            ).run(changed_selected, phase="images")

            self.assertEqual(len(provider.calls) - original_calls, 4)

    def test_uncertain_asset_requires_explicit_retry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp))
            plan = build_plan(project)
            manifest = ManifestStore(project / "production-manifest.json", project)
            anchors = AnchorRegistry(project / "production-anchors.json")
            selected = {"scene-001:primary"}
            bad_provider = FakeImageProvider(fail=True)
            runner = ProductionRunner(
                plan=plan,
                manifest=manifest,
                anchors=anchors,
                settings=ProductionSettings(image_provider="google"),
                image_provider=bad_provider,
            )
            with self.assertRaisesRegex(ProductionError, "Image generation failed"):
                runner.run(selected, phase="images")
            self.assertEqual(manifest.get("scene-001:primary")["status"], "uncertain")

            good_provider = FakeImageProvider()
            runner.image_provider = good_provider
            with self.assertRaisesRegex(ProductionError, "explicit retry"):
                runner.run(selected, phase="images")
            self.assertEqual(len(good_provider.calls), 0)

            manifest.reset_for_retry("scene-001:primary")
            runner.run(selected, phase="images")
            self.assertEqual(len(good_provider.calls), 1)


    def test_anchor_deduplicates_previous_frame_and_subject_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp))
            plan = build_plan(project)
            manifest = ManifestStore(project / "production-manifest.json", project)
            anchors = AnchorRegistry(project / "production-anchors.json")
            provider = FakeImageProvider()
            runner = ProductionRunner(
                plan=plan,
                manifest=manifest,
                anchors=anchors,
                settings=ProductionSettings(),
                image_provider=provider,
            )
            runner.run({"scene-001:primary"}, phase="images")
            anchor_record = manifest.get("scene-001:primary")
            anchors.set_subject(
                "person",
                "scene-001:primary",
                output_sha256=anchor_record["output_sha256"],
                fingerprint=anchor_record["fingerprint"],
            )
            refs = image_references_for_node(
                plan.node_by_id["scene-002:primary"],
                plan=plan,
                manifest=manifest,
                anchors=anchors,
            )
            self.assertEqual(len(refs), 1)
            self.assertIn("previous generated visual state", refs[0].role)
            self.assertIn("approved continuity anchor", refs[0].role)

    def test_optional_subject_sheet_is_attached_after_scene_continuity_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp))
            continuity = json.loads((project / "continuity.json").read_text())
            continuity["subjects"]["person"]["image_path"] = "images/subjects/person.png"
            write_json(project / "continuity.json", continuity)
            sheet = project / "images/subjects/person.png"
            sheet.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (16, 16), (12, 34, 56)).save(sheet)

            plan = build_plan(project)
            manifest = ManifestStore(project / "production-manifest.json", project)
            anchors = AnchorRegistry(project / "production-anchors.json")
            provider = FakeImageProvider()
            runner = ProductionRunner(
                plan=plan,
                manifest=manifest,
                anchors=anchors,
                settings=ProductionSettings(),
                image_provider=provider,
            )
            runner.run({"scene-001:primary"}, phase="images")

            refs = image_references_for_node(
                plan.node_by_id["scene-002:primary"],
                plan=plan,
                manifest=manifest,
                anchors=anchors,
            )
            self.assertEqual([ref.asset_id for ref in refs], ["scene-001:primary", "subject:person"])
            self.assertIn("previous generated visual state", refs[0].role)
            self.assertIn("canonical identity sheet", refs[1].role)

    def test_missing_optional_subject_sheet_is_skipped_without_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp))
            continuity = json.loads((project / "continuity.json").read_text())
            continuity["subjects"]["person"]["image_path"] = "images/subjects/missing.png"
            write_json(project / "continuity.json", continuity)
            plan = build_plan(project)
            refs = image_references_for_node(
                plan.node_by_id["scene-001:primary"],
                plan=plan,
                manifest=ManifestStore(project / "production-manifest.json", project),
                anchors=AnchorRegistry(project / "production-anchors.json"),
            )
            self.assertEqual(refs, ())

    def test_subject_sheet_bytes_participate_in_asset_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp))
            continuity = json.loads((project / "continuity.json").read_text())
            continuity["subjects"]["person"]["image_path"] = "images/subjects/person.png"
            write_json(project / "continuity.json", continuity)
            sheet = project / "images/subjects/person.png"
            sheet.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (16, 16), (10, 20, 30)).save(sheet)

            plan = build_plan(project)
            manifest = ManifestStore(project / "production-manifest.json", project)
            anchors = AnchorRegistry(project / "production-anchors.json")
            provider = FakeImageProvider()
            runner = ProductionRunner(
                plan=plan,
                manifest=manifest,
                anchors=anchors,
                settings=ProductionSettings(),
                image_provider=provider,
            )
            runner.run({"scene-001:primary"}, phase="images")
            first_fingerprint = manifest.get("scene-001:primary")["fingerprint"]

            Image.new("RGB", (16, 16), (40, 50, 60)).save(sheet)
            changed_plan = build_plan(project)
            changed_runner = ProductionRunner(
                plan=changed_plan,
                manifest=manifest,
                anchors=anchors,
                settings=ProductionSettings(),
                image_provider=provider,
            )
            changed_runner.run({"scene-001:primary"}, phase="images")
            second_fingerprint = manifest.get("scene-001:primary")["fingerprint"]
            self.assertNotEqual(first_fingerprint, second_fingerprint)
            self.assertEqual(len(provider.calls), 2)

    def test_flow_video_run_resumes_existing_job_without_resubmission(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp))
            video_prompts = project / "bin/video-prompts.json"
            write_json(
                video_prompts,
                {
                    "version": 1,
                    "scenes": {
                        "scene-002": {
                            "prompt": "move naturally from A to B",
                            "provider": "flow",
                            "duration": 6,
                        }
                    },
                },
            )
            plan = build_plan(project, video_prompts_path=video_prompts)
            manifest = ManifestStore(project / "production-manifest.json", project)
            anchors = AnchorRegistry(project / "production-anchors.json")
            image_provider = FakeImageProvider()
            image_runner = ProductionRunner(
                plan=plan,
                manifest=manifest,
                anchors=anchors,
                settings=ProductionSettings(),
                image_provider=image_provider,
            )
            image_runner.run(
                select_assets(plan, scene_ids=("scene-002",), phase="images"),
                phase="images",
            )

            waiting_flow = FakeFlowVideoProvider(finish=False)
            first_runner = ProductionRunner(
                plan=plan,
                manifest=manifest,
                anchors=anchors,
                settings=ProductionSettings(flow_poll_seconds=0.001, flow_poll_timeout=0.005),
                image_provider=image_provider,
                flow_video_provider=waiting_flow,
                video_verifier=lambda path: None if path.read_bytes() == b"fake-video" else (_ for _ in ()).throw(ValueError()),
            )
            with self.assertRaisesRegex(ProductionError, "still pending"):
                first_runner.run({"scene-002:video"}, phase="videos")
            self.assertEqual(waiting_flow.submit_calls, 1)
            self.assertTrue(waiting_flow.submit_keys[0].startswith("kathamind-"))
            self.assertIn("-video-", waiting_flow.submit_keys[0])
            self.assertEqual(manifest.get("scene-002:video")["status"], "submitted")
            self.assertEqual(manifest.get("scene-002:video")["remote_job_id"], "job-123")

            finishing_flow = FakeFlowVideoProvider(finish=True)
            second_runner = ProductionRunner(
                plan=plan,
                manifest=manifest,
                anchors=anchors,
                settings=ProductionSettings(flow_poll_seconds=0.001, flow_poll_timeout=1),
                image_provider=image_provider,
                flow_video_provider=finishing_flow,
                video_verifier=lambda path: None if path.read_bytes() == b"fake-video" else (_ for _ in ()).throw(ValueError()),
            )
            result = second_runner.run({"scene-002:video"}, phase="videos")
            self.assertEqual(finishing_flow.submit_calls, 0)
            self.assertEqual(result.completed, ("scene-002:video",))
            self.assertEqual(manifest.get("scene-002:video")["status"], "complete")

    def test_video_phase_refuses_stale_image_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp))
            video_prompts = project / "bin/video-prompts.json"
            write_json(
                video_prompts,
                {"scenes": {"scene-002": {"prompt": "move A to B", "duration": 6}}},
            )
            plan = build_plan(project, video_prompts_path=video_prompts)
            manifest = ManifestStore(project / "production-manifest.json", project)
            anchors = AnchorRegistry(project / "production-anchors.json")
            image_provider = FakeImageProvider()
            runner = ProductionRunner(
                plan=plan,
                manifest=manifest,
                anchors=anchors,
                settings=ProductionSettings(image_provider="google"),
                image_provider=image_provider,
                flow_video_provider=FakeFlowVideoProvider(finish=True),
                video_verifier=lambda path: None,
            )
            runner.run(
                select_assets(plan, scene_ids=("scene-002",), phase="images"),
                phase="images",
            )
            source = json.loads((project / "scenes.json").read_text())
            source["scenes"][0]["image_prompt"] = "changed ancestor"
            write_json(project / "scenes.json", source)
            changed_plan = build_plan(project, video_prompts_path=video_prompts)
            changed_runner = ProductionRunner(
                plan=changed_plan,
                manifest=manifest,
                anchors=anchors,
                settings=ProductionSettings(image_provider="google"),
                image_provider=image_provider,
                flow_video_provider=FakeFlowVideoProvider(finish=True),
                video_verifier=lambda path: None,
            )
            with self.assertRaisesRegex(ProductionError, "stale"):
                changed_runner.run({"scene-002:video"}, phase="videos")

    def test_flow_image_uncertain_state_replays_same_idempotency_key_without_retry_reset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp))
            plan = build_plan(project)
            manifest = ManifestStore(project / "production-manifest.json", project)
            anchors = AnchorRegistry(project / "production-anchors.json")
            bad = FakeImageProvider(fail=True)
            runner = ProductionRunner(
                plan=plan,
                manifest=manifest,
                anchors=anchors,
                settings=ProductionSettings(image_provider="flow"),
                image_provider=bad,
            )
            with self.assertRaises(ProductionError):
                runner.run({"scene-001:primary"}, phase="images")
            first_key = bad.calls[0]["idempotency_key"]
            self.assertIsNotNone(first_key)
            with self.assertRaisesRegex(ValueError, "durable idempotency key"):
                manifest.reset_for_retry("scene-001:primary")

            good = FakeImageProvider()
            runner.image_provider = good
            result = runner.run({"scene-001:primary"}, phase="images")
            self.assertEqual(result.completed, ("scene-001:primary",))
            self.assertEqual(good.calls[0]["idempotency_key"], first_key)
            self.assertEqual(int(manifest.get("scene-001:primary").get("attempts") or 0), 0)

    def test_flow_image_high_traffic_uses_fresh_deterministic_recovery_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp))
            plan = build_plan(project)
            manifest = ManifestStore(project / "production-manifest.json", project)
            provider = SequencedFlowImageProvider(["high_traffic", "success"])
            runner = ProductionRunner(
                plan=plan,
                manifest=manifest,
                anchors=AnchorRegistry(project / "production-anchors.json"),
                settings=ProductionSettings(image_provider="flow"),
                image_provider=provider,
            )
            with patch("scripts.production.runner.time.sleep"):
                result = runner.run({"scene-001:primary"}, phase="images")
            self.assertEqual(result.completed, ("scene-001:primary",))
            first_key, recovery_key = [call["idempotency_key"] for call in provider.calls]
            self.assertEqual(
                recovery_key,
                flow_recovery_idempotency_key(first_key, "PUBLIC_ERROR_HIGH_TRAFFIC"),
            )
            record = manifest.get("scene-001:primary")
            self.assertEqual(record["status"], "complete")
            self.assertEqual(int(record.get("attempts") or 0), 0)

    def test_flow_image_ambiguous_failure_after_recovery_replays_same_recovery_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp))
            plan = build_plan(project)
            manifest = ManifestStore(project / "production-manifest.json", project)
            provider = SequencedFlowImageProvider(["high_traffic", "ambiguous"])
            runner = ProductionRunner(
                plan=plan,
                manifest=manifest,
                anchors=AnchorRegistry(project / "production-anchors.json"),
                settings=ProductionSettings(image_provider="flow"),
                image_provider=provider,
            )
            with patch("scripts.production.runner.time.sleep"):
                with self.assertRaises(ProductionError):
                    runner.run({"scene-001:primary"}, phase="images")
            recovery_key = provider.calls[-1]["idempotency_key"]
            uncertain = manifest.get("scene-001:primary")
            self.assertEqual(uncertain["status"], "uncertain")
            self.assertEqual(uncertain["idempotency_key"], recovery_key)
            self.assertIsNone(uncertain.get("provider_rejection"))

            good = SequencedFlowImageProvider(["success"])
            runner.image_provider = good
            result = runner.run({"scene-001:primary"}, phase="images")
            self.assertEqual(result.completed, ("scene-001:primary",))
            self.assertEqual(good.calls[0]["idempotency_key"], recovery_key)

    def test_flow_image_legacy_uncertain_high_traffic_record_advances_to_recovery_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp))
            plan = build_plan(project)
            manifest = ManifestStore(project / "production-manifest.json", project)
            bad = FakeImageProvider(fail=True)
            runner = ProductionRunner(
                plan=plan,
                manifest=manifest,
                anchors=AnchorRegistry(project / "production-anchors.json"),
                settings=ProductionSettings(image_provider="flow"),
                image_provider=bad,
            )
            with self.assertRaises(ProductionError):
                runner.run({"scene-001:primary"}, phase="images")
            old = manifest.get("scene-001:primary")
            old_key = old["idempotency_key"]
            manifest.update(
                "scene-001:primary",
                status="uncertain",
                error="HTTP 400 PUBLIC_ERROR_HIGH_TRAFFIC",
            )
            good = SequencedFlowImageProvider(["success"])
            runner.image_provider = good
            result = runner.run({"scene-001:primary"}, phase="images")
            self.assertEqual(result.completed, ("scene-001:primary",))
            self.assertEqual(
                good.calls[0]["idempotency_key"],
                flow_recovery_idempotency_key(old_key, "PUBLIC_ERROR_HIGH_TRAFFIC"),
            )

    def test_anchor_approval_is_invalid_after_anchor_asset_regeneration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp))
            plan = build_plan(project)
            manifest = ManifestStore(project / "production-manifest.json", project)
            anchors = AnchorRegistry(project / "production-anchors.json")
            provider = FakeImageProvider()
            runner = ProductionRunner(
                plan=plan,
                manifest=manifest,
                anchors=anchors,
                settings=ProductionSettings(image_provider="google"),
                image_provider=provider,
            )
            runner.run({"scene-001:primary"}, phase="images")
            approved = manifest.get("scene-001:primary")
            anchors.set_subject(
                "person",
                "scene-001:primary",
                output_sha256=approved["output_sha256"],
                fingerprint=approved["fingerprint"],
            )

            source = json.loads((project / "scenes.json").read_text())
            source["scenes"][0]["image_prompt"] = "regenerated anchor prompt"
            write_json(project / "scenes.json", source)
            changed_plan = build_plan(project)
            changed_runner = ProductionRunner(
                plan=changed_plan,
                manifest=manifest,
                anchors=anchors,
                settings=ProductionSettings(image_provider="google"),
                image_provider=provider,
            )
            changed_runner.run({"scene-001:primary"}, phase="images")
            with self.assertRaisesRegex(Exception, "changed after approval"):
                image_references_for_node(
                    changed_plan.node_by_id["scene-002:primary"],
                    plan=changed_plan,
                    manifest=manifest,
                    anchors=anchors,
                )

    def test_reference_budget_overflow_fails_instead_of_dropping_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp))
            continuity = json.loads((project / "continuity.json").read_text())
            for index in range(2, 6):
                continuity["subjects"][f"person{index}"] = {"role": "recurring"}
            write_json(project / "continuity.json", continuity)
            scenes = json.loads((project / "scenes.json").read_text())
            scenes["scenes"][1]["subjects"] = ["person", "person2", "person3", "person4", "person5"]
            write_json(project / "scenes.json", scenes)
            scenes["scenes"][3]["subjects"] = ["person", "person2", "person3", "person4", "person5"]
            write_json(project / "scenes.json", scenes)
            plan = build_plan(project)
            manifest = ManifestStore(project / "production-manifest.json", project)
            anchors = AnchorRegistry(project / "production-anchors.json")
            provider = FakeImageProvider()
            runner = ProductionRunner(
                plan=plan,
                manifest=manifest,
                anchors=anchors,
                settings=ProductionSettings(image_provider="google"),
                image_provider=provider,
            )
            runner.run(select_assets(plan, phase="images"), phase="images")
            assignments = {
                "person": "scene-001:primary",
                "person2": "scene-002:primary",
                "person3": "scene-002:c01",
                "person4": "scene-003:primary",
                "person5": "scene-004:primary",
            }
            for subject, asset_id in assignments.items():
                record = manifest.get(asset_id)
                anchors.set_subject(
                    subject,
                    asset_id,
                    output_sha256=record["output_sha256"],
                    fingerprint=record["fingerprint"],
                )
            with self.assertRaisesRegex(ReferenceError, "refusing to silently drop"):
                image_references_for_node(
                    plan.node_by_id["scene-004:c02"],
                    plan=plan,
                    manifest=manifest,
                    anchors=anchors,
                )

    def test_project_lock_rejects_second_writer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lock_path = Path(tmp) / ".production.lock"
            with ProjectLock(lock_path):
                with self.assertRaisesRegex(RuntimeError, "already writing"):
                    with ProjectLock(lock_path):
                        pass

    def test_retry_refuses_to_erase_active_remote_job(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp))
            manifest = ManifestStore(project / "production-manifest.json", project)
            manifest.update(
                "scene-001:video",
                status="submitted",
                remote_job_id="job-live",
                idempotency_key="key-live",
            )
            with self.assertRaisesRegex(ValueError, "active remote state"):
                manifest.reset_for_retry("scene-001:video")

    def test_flow_video_http_submission_sends_idempotency_header(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = FlowMediaCache(Path(tmp) / "cache.json")
            provider = FlowVideoProvider(base_url="http://flow.invalid", cache=cache)
            start = Path(tmp) / "start.png"
            end = Path(tmp) / "end.png"
            Image.new("RGB", (2, 2)).save(start)
            Image.new("RGB", (2, 2)).save(end)
            with (
                patch.object(provider, "preflight"),
                patch.object(provider, "check_credits"),
                patch.object(provider, "_upload", side_effect=[("start-id", False), ("end-id", False)]),
                patch(
                    "scripts.production.providers._request_json",
                    return_value={"job_id": "job-1", "status": "queued", "data": []},
                ) as request_json,
            ):
                provider.submit(
                    prompt="animate",
                    start_frame=start,
                    end_frame=end,
                    duration=6,
                    aspect_ratio="16:9",
                    model="omni_flash",
                    idempotency_key="video-key-1",
                )
            self.assertEqual(
                request_json.call_args.kwargs["headers"]["Idempotency-Key"],
                "video-key-1",
            )

    def test_flow_video_replay_skips_credit_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = FlowMediaCache(Path(tmp) / "cache.json")
            provider = FlowVideoProvider(base_url="http://flow.invalid", cache=cache)
            start = Path(tmp) / "start.png"
            Image.new("RGB", (2, 2)).save(start)
            with (
                patch.object(provider, "preflight"),
                patch.object(provider, "check_credits") as check_credits,
                patch.object(provider, "_upload", return_value=("start-id", False)),
                patch(
                    "scripts.production.providers._request_json",
                    return_value={"job_id": "job-1", "status": "queued", "data": []},
                ),
            ):
                provider.submit(
                    prompt="resume same request",
                    start_frame=start,
                    end_frame=None,
                    duration=6,
                    aspect_ratio="16:9",
                    model="omni_flash",
                    idempotency_key="same-paid-request",
                    check_credits=False,
                )
            check_credits.assert_not_called()

    def test_flow_upload_readiness_exhaustion_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = FlowMediaCache(Path(tmp) / "cache.json")
            provider = FlowVideoProvider(base_url="http://flow.invalid", cache=cache)
            start = Path(tmp) / "start.png"
            Image.new("RGB", (2, 2)).save(start)
            with (
                patch.object(provider, "_media_valid", return_value=False),
                patch("scripts.production.providers.time.sleep"),
                patch(
                    "scripts.production.providers._request_json",
                    return_value={"media_id": "never-ready"},
                ),
            ):
                with self.assertRaisesRegex(Exception, "never became ready"):
                    provider._upload(start, "start frame")
            self.assertIsNone(cache.get(hashlib.sha256(start.read_bytes()).hexdigest()))

    def test_flow_credit_lookup_failure_fails_closed(self) -> None:
        provider = FlowVideoProvider(base_url="http://flow.invalid")
        with patch(
            "scripts.production.providers._request_json",
            side_effect=RuntimeError("credits unavailable"),
        ):
            with self.assertRaisesRegex(Exception, "Could not verify Flow credits"):
                provider.check_credits(6)

    def test_runner_credit_prepare_failure_stays_blocked_and_rechecks_on_rerun(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp))
            video_prompts = project / "bin/video-prompts.json"
            write_json(
                video_prompts,
                {"scenes": {"scene-002": {"prompt": "move A to B", "duration": 6}}},
            )
            plan = build_plan(project, video_prompts_path=video_prompts)
            manifest = ManifestStore(project / "production-manifest.json", project)
            anchors = AnchorRegistry(project / "production-anchors.json")
            image_provider = FakeImageProvider()
            ProductionRunner(
                plan=plan,
                manifest=manifest,
                anchors=anchors,
                settings=ProductionSettings(image_provider="google"),
                image_provider=image_provider,
            ).run(
                select_assets(plan, scene_ids=("scene-002",), phase="images"),
                phase="images",
            )

            blocked_flow = FakeFlowVideoProvider(finish=True)
            runner = ProductionRunner(
                plan=plan,
                manifest=manifest,
                anchors=anchors,
                settings=ProductionSettings(),
                image_provider=image_provider,
                flow_video_provider=blocked_flow,
                video_verifier=lambda path: None,
            )
            with patch.object(
                blocked_flow,
                "prepare",
                side_effect=RuntimeError("credit lookup unavailable"),
            ):
                with self.assertRaisesRegex(ProductionError, "pre-submit preparation"):
                    runner.run({"scene-002:video"}, phase="videos")
            blocked = manifest.get("scene-002:video")
            self.assertEqual(blocked["status"], "blocked")
            self.assertNotIn("idempotency_key", blocked)
            self.assertEqual(int(blocked.get("attempts") or 0), 0)

            good_flow = FakeFlowVideoProvider(finish=True)
            resumed = ProductionRunner(
                plan=plan,
                manifest=manifest,
                anchors=anchors,
                settings=ProductionSettings(flow_poll_seconds=0.001, flow_poll_timeout=1),
                image_provider=image_provider,
                flow_video_provider=good_flow,
                video_verifier=lambda path: None,
            )
            resumed.run({"scene-002:video"}, phase="videos")
            self.assertEqual(good_flow.prepare_calls, 1)
            self.assertEqual(good_flow.prepare_checks, [True])
            self.assertEqual(int(manifest.get("scene-002:video").get("attempts") or 0), 0)

    def test_runner_media_prepare_failure_stays_blocked_and_never_enters_uncertain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp))
            video_prompts = project / "bin/video-prompts.json"
            write_json(
                video_prompts,
                {"scenes": {"scene-002": {"prompt": "move A to B", "duration": 6}}},
            )
            plan = build_plan(project, video_prompts_path=video_prompts)
            manifest = ManifestStore(project / "production-manifest.json", project)
            anchors = AnchorRegistry(project / "production-anchors.json")
            image_provider = FakeImageProvider()
            ProductionRunner(
                plan=plan,
                manifest=manifest,
                anchors=anchors,
                settings=ProductionSettings(image_provider="google"),
                image_provider=image_provider,
            ).run(
                select_assets(plan, scene_ids=("scene-002",), phase="images"),
                phase="images",
            )

            blocked_flow = FakeFlowVideoProvider(finish=True)
            runner = ProductionRunner(
                plan=plan,
                manifest=manifest,
                anchors=anchors,
                settings=ProductionSettings(),
                image_provider=image_provider,
                flow_video_provider=blocked_flow,
                video_verifier=lambda path: None,
            )
            with patch.object(
                blocked_flow,
                "prepare",
                side_effect=RuntimeError("start frame media never became ready"),
            ):
                with self.assertRaisesRegex(ProductionError, "pre-submit preparation"):
                    runner.run({"scene-002:video"}, phase="videos")
            record = manifest.get("scene-002:video")
            self.assertEqual(record["status"], "blocked")
            self.assertNotEqual(record["status"], "uncertain")
            self.assertNotIn("idempotency_key", record)
            self.assertEqual(int(record.get("attempts") or 0), 0)

    def test_ambiguous_paid_post_failure_replays_same_request_without_reprepare(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp))
            video_prompts = project / "bin/video-prompts.json"
            write_json(
                video_prompts,
                {"scenes": {"scene-002": {"prompt": "move A to B", "duration": 6}}},
            )
            plan = build_plan(project, video_prompts_path=video_prompts)
            manifest = ManifestStore(project / "production-manifest.json", project)
            anchors = AnchorRegistry(project / "production-anchors.json")
            image_provider = FakeImageProvider()
            ProductionRunner(
                plan=plan,
                manifest=manifest,
                anchors=anchors,
                settings=ProductionSettings(image_provider="google"),
                image_provider=image_provider,
            ).run(
                select_assets(plan, scene_ids=("scene-002",), phase="images"),
                phase="images",
            )

            ambiguous_flow = FakeFlowVideoProvider(finish=True)
            runner = ProductionRunner(
                plan=plan,
                manifest=manifest,
                anchors=anchors,
                settings=ProductionSettings(),
                image_provider=image_provider,
                flow_video_provider=ambiguous_flow,
                video_verifier=lambda path: None,
            )
            with patch.object(
                ambiguous_flow,
                "submit_prepared",
                side_effect=RuntimeError("connection reset after paid POST"),
            ):
                with self.assertRaisesRegex(ProductionError, "Flow submission failed"):
                    runner.run({"scene-002:video"}, phase="videos")
            uncertain = manifest.get("scene-002:video")
            first_key = uncertain["idempotency_key"]
            first_request = dict(uncertain["remote_request"])
            self.assertEqual(uncertain["status"], "uncertain")
            self.assertEqual(ambiguous_flow.prepare_calls, 1)
            self.assertEqual(int(uncertain.get("attempts") or 0), 0)

            replay_flow = FakeFlowVideoProvider(finish=True)
            replay = ProductionRunner(
                plan=plan,
                manifest=manifest,
                anchors=anchors,
                settings=ProductionSettings(flow_poll_seconds=0.001, flow_poll_timeout=1),
                image_provider=image_provider,
                flow_video_provider=replay_flow,
                video_verifier=lambda path: None,
            )
            replay.run({"scene-002:video"}, phase="videos")
            self.assertEqual(replay_flow.prepare_calls, 0)
            self.assertEqual(replay_flow.submit_calls, 1)
            self.assertEqual(replay_flow.submit_keys, [first_key])
            self.assertEqual(int(manifest.get("scene-002:video").get("attempts") or 0), 0)
            self.assertEqual(manifest.get("scene-002:video")["remote_request"], first_request)

    def test_terminal_flow_failure_is_not_retried_as_a_new_creative_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp))
            video_prompts = project / "bin/video-prompts.json"
            write_json(
                video_prompts,
                {"scenes": {"scene-002": {"prompt": "move A to B", "duration": 6}}},
            )
            plan = build_plan(project, video_prompts_path=video_prompts)
            manifest = ManifestStore(project / "production-manifest.json", project)
            anchors = AnchorRegistry(project / "production-anchors.json")
            image_provider = FakeImageProvider()
            ProductionRunner(
                plan=plan,
                manifest=manifest,
                anchors=anchors,
                settings=ProductionSettings(image_provider="google"),
                image_provider=image_provider,
            ).run(
                select_assets(plan, scene_ids=("scene-002",), phase="images"),
                phase="images",
            )

            failed_flow = FakeFlowVideoProvider(finish=False)
            failed_flow.poll_once = lambda _job_id: VideoPoll(
                status="failed", error="terminal remote failure"
            )
            failed_runner = ProductionRunner(
                plan=plan,
                manifest=manifest,
                anchors=anchors,
                settings=ProductionSettings(flow_poll_seconds=0.001, flow_poll_timeout=1),
                image_provider=image_provider,
                flow_video_provider=failed_flow,
                video_verifier=lambda path: None,
            )
            with self.assertRaisesRegex(ProductionError, "Flow job failed"):
                failed_runner.run({"scene-002:video"}, phase="videos")
            first_key = manifest.get("scene-002:video")["idempotency_key"]
            self.assertEqual(manifest.get("scene-002:video")["status"], "failed")
            self.assertTrue(first_key)
            with self.assertRaisesRegex(ValueError, "separate candidate"):
                manifest.reset_for_retry("scene-002:video")

            success_flow = FakeFlowVideoProvider(finish=True)
            success_runner = ProductionRunner(
                plan=plan,
                manifest=manifest,
                anchors=anchors,
                settings=ProductionSettings(flow_poll_seconds=0.001, flow_poll_timeout=1),
                image_provider=image_provider,
                flow_video_provider=success_flow,
                video_verifier=lambda path: None,
            )
            with self.assertRaisesRegex(ProductionError, "previously failed"):
                success_runner.run({"scene-002:video"}, phase="videos")
            self.assertEqual(success_flow.submit_calls, 0)

    def test_non_idempotent_submitting_state_can_be_explicitly_abandoned_for_retry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp))
            manifest = ManifestStore(project / "production-manifest.json", project)
            manifest.update(
                "scene-001:video",
                status="submitting",
                provider="google",
                fingerprint="fp-1",
            )
            manifest.reset_for_retry("scene-001:video")
            record = manifest.get("scene-001:video")
            self.assertEqual(record["status"], "planned")
            self.assertEqual(len(record["history"]), 1)

    def test_flow_idempotency_keys_are_project_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_a = make_project(root)
            project_b = root / "story-copy"
            project_b.mkdir()
            (project_b / "scenes.json").write_bytes((project_a / "scenes.json").read_bytes())
            (project_b / "continuity.json").write_bytes((project_a / "continuity.json").read_bytes())
            (project_b / "session.json").write_bytes((project_a / "session.json").read_bytes())

            keys = []
            for project in (project_a, project_b):
                plan = build_plan(project)
                manifest = ManifestStore(project / "production-manifest.json", project)
                anchors = AnchorRegistry(project / "production-anchors.json")
                provider = FakeImageProvider()
                ProductionRunner(
                    plan=plan,
                    manifest=manifest,
                    anchors=anchors,
                    settings=ProductionSettings(image_provider="flow"),
                    image_provider=provider,
                ).run({"scene-001:primary"}, phase="images")
                keys.append(provider.calls[0]["idempotency_key"])
            self.assertNotEqual(keys[0], keys[1])

    def test_flow_image_http_submission_sends_idempotency_header(self) -> None:
        provider = FlowImageProvider()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out.png"
            with (
                patch.object(provider.flow, "require_ready"),
                patch.object(provider.flow, "normalize_model", return_value="gem_pix_2"),
                patch.object(provider.flow, "resolve_base_url", return_value="http://flow.invalid"),
                patch.object(provider.flow, "_download_image_as_png") as download,
                patch(
                    "scripts.production.providers._request_json",
                    return_value={"data": [{"url": "http://example.invalid/image.png"}]},
                ) as request_json,
            ):
                provider.generate(
                    prompt="still",
                    output=output,
                    references=(),
                    model="pro",
                    aspect_ratio="16:9",
                    idempotency_key="image-key-1",
                )
            download.assert_called_once()
            self.assertEqual(
                request_json.call_args.kwargs["headers"]["Idempotency-Key"],
                "image-key-1",
            )

    def test_flow_image_provider_classifies_high_traffic_400_as_no_result_rejection(self) -> None:
        provider = FlowImageProvider()
        with tempfile.TemporaryDirectory() as tmp:
            error = urllib.error.HTTPError(
                "http://flow.invalid/v1/images/generations",
                400,
                "Bad Request",
                {},
                io.BytesIO(b'{"detail":"Resource exhausted (PUBLIC_ERROR_HIGH_TRAFFIC)"}'),
            )
            with (
                patch.object(provider.flow, "require_ready"),
                patch.object(provider.flow, "normalize_model", return_value="gem_pix_2"),
                patch.object(provider.flow, "resolve_base_url", return_value="http://flow.invalid"),
                patch("scripts.production.providers._request_json", side_effect=error),
            ):
                with self.assertRaises(ProviderNoResultRejection) as caught:
                    provider.generate(
                        prompt="still",
                        output=Path(tmp) / "out.png",
                        references=(),
                        model="pro",
                        aspect_ratio="16:9",
                        idempotency_key="image-key-1",
                    )
            self.assertEqual(caught.exception.code, "PUBLIC_ERROR_HIGH_TRAFFIC")

    def test_explicit_missing_video_prompt_path_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp))
            with self.assertRaisesRegex(PlanError, "does not exist"):
                build_plan(project, video_prompts_path=project / "missing.json")


if __name__ == "__main__":
    unittest.main()


from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from studio.core.state import StageState
from studio.core.config import ProductionConfig
from studio.pipeline_scripts import production


class ProductionPipelineTests(unittest.TestCase):
    def test_character_phase_is_exposed_without_marking_scene_stage_complete(self) -> None:
        project = Path("/tmp/story-project")
        with (
            patch.object(production, "resolve_project_dir", return_value=project),
            patch.object(
                production,
                "stage_state",
                return_value=StageState("illustrate", False, ("scene-001.image_path",)),
            ),
            patch.object(production, "_run_script") as run_script,
            patch.object(production, "update_status") as update_status,
        ):
            production.run_stage(
                project,
                "illustrate",
                illustration_phase="characters",
            )

        run_script.assert_called_once_with(
            project,
            "images/illustrate.py",
            "--phase",
            "characters",
        )
        update_status.assert_not_called()

    def test_partial_illustration_phase_rejected_for_other_stage(self) -> None:
        with patch.object(
            production, "resolve_project_dir", return_value=Path("/tmp/story-project")
        ):
            with self.assertRaisesRegex(production.PipelineError, "only for the illustrate"):
                production.run_stage(
                    "/tmp/story-project",
                    "voice",
                    illustration_phase="characters",
                )

    def test_render_honors_disabled_subtitles_and_zoom(self) -> None:
        project = Path("/tmp/story-project")
        incomplete = StageState("render", False, ("output/final-video.mp4",))
        complete = StageState("render", True, ())
        with (
            patch.object(production, "resolve_project_dir", return_value=project),
            patch.object(production, "stage_state", side_effect=[incomplete, complete]),
            patch.object(production, "load_session", return_value={}),
            patch.object(
                production,
                "load_production_config",
                return_value=ProductionConfig("cloudflare", "model", False, False),
            ),
            patch.object(production, "_run_script") as run_script,
            patch.object(production, "update_status"),
        ):
            production.run_stage(project, "render")

        self.assertEqual(
            [
                unittest.mock.call(
                    project,
                    "rendering/scenes.py",
                    "--skip-subtitles",
                    "--no-motion",
                ),
                unittest.mock.call(project, "rendering/final.py"),
            ],
            run_script.call_args_list,
        )

    def test_outer_image_overrides_are_forwarded_to_illustrate(self) -> None:
        project = Path("/tmp/story-project")
        incomplete = StageState("illustrate", False, ("scene-001.image_path",))
        complete = StageState("illustrate", True, ())
        with (
            patch.object(production, "resolve_project_dir", return_value=project),
            patch.object(production, "stage_state", side_effect=[incomplete, complete]),
            patch.object(production, "_run_script") as run_script,
            patch.object(production, "update_status"),
        ):
            production.run_stage(
                project,
                "illustrate",
                image_provider="google",
                image_model="gemini-3.1-flash-image",
            )

        run_script.assert_called_once_with(
            project,
            "images/illustrate.py",
            "--phase",
            "all",
            "--provider",
            "google",
            "--model",
            "gemini-3.1-flash-image",
        )

    def test_override_cannot_be_silently_ignored_by_complete_stage(self) -> None:
        project = Path("/tmp/story-project")
        with (
            patch.object(production, "resolve_project_dir", return_value=project),
            patch.object(
                production,
                "stage_state",
                return_value=StageState("illustrate", True, ()),
            ),
            self.assertRaisesRegex(production.PipelineError, "use --force"),
        ):
            production.run_stage(
                project,
                "illustrate",
                image_model="@cf/black-forest-labs/flux-2-dev",
            )

    def test_render_override_is_passed_to_config_resolution(self) -> None:
        project = Path("/tmp/story-project")
        incomplete = StageState("render", False, ("output/final-video.mp4",))
        complete = StageState("render", True, ())
        with (
            patch.object(production, "resolve_project_dir", return_value=project),
            patch.object(production, "stage_state", side_effect=[incomplete, complete]),
            patch.object(production, "load_session", return_value={}),
            patch.object(
                production,
                "load_production_config",
                return_value=ProductionConfig("cloudflare", "model", True, False),
            ) as load_config,
            patch.object(production, "_run_script"),
            patch.object(production, "update_status"),
        ):
            production.run_stage(project, "render", subtitles=True, zoom=False)

        load_config.assert_called_once_with({}, subtitles=True, zoom=False)

    def test_render_override_rejects_cached_scene_clips_without_force(self) -> None:
        with TemporaryDirectory() as tmp:
            project = Path(tmp)
            clips = project / "temp" / "scenes"
            clips.mkdir(parents=True)
            (clips / "scene-001.mp4").write_bytes(b"cached")
            with (
                patch.object(production, "resolve_project_dir", return_value=project),
                patch.object(
                    production,
                    "stage_state",
                    return_value=StageState("render", False, ("output/final-video.mp4",)),
                ),
                self.assertRaisesRegex(production.PipelineError, "cached scene clips"),
            ):
                production.run_stage(project, "render", subtitles=True)

    def test_image_override_rejects_partial_scene_cache_without_force(self) -> None:
        with TemporaryDirectory() as tmp:
            project = Path(tmp)
            images = project / "images"
            images.mkdir()
            (images / "scene-001.png").write_bytes(b"cached")
            with (
                patch.object(production, "resolve_project_dir", return_value=project),
                patch.object(
                    production,
                    "stage_state",
                    return_value=StageState("illustrate", False, ("scene-002.image_path",)),
                ),
                self.assertRaisesRegex(production.PipelineError, "cached images"),
            ):
                production.run_stage(
                    project,
                    "illustrate",
                    image_model="@cf/black-forest-labs/flux-2-dev",
                )

from pathlib import Path
import unittest
from unittest.mock import patch

from studio.core.state import StageState
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
            "images/cloudflare_image_gen.py",
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

from pathlib import Path
import unittest
from unittest.mock import patch

from studio import pipeline_cli


class PipelineCliTests(unittest.TestCase):
    def test_run_forwards_inner_pipeline_overrides(self) -> None:
        with patch.object(pipeline_cli, "run_pipeline") as run_pipeline:
            result = pipeline_cli.main(
                [
                    "run",
                    "library/story",
                    "--image-provider",
                    "google",
                    "--image-model",
                    "gemini-3.1-flash-image",
                    "--subtitles",
                    "--no-zoom",
                    "--force",
                ]
            )

        self.assertEqual(0, result)
        run_pipeline.assert_called_once_with(
            Path("library/story"),
            from_stage=None,
            force_stage=None,
            force=True,
            image_provider="google",
            image_model="gemini-3.1-flash-image",
            subtitles=True,
            zoom=False,
            closing_fade=None,
        )

    def test_force_stage_is_repeatable(self) -> None:
        with patch.object(pipeline_cli, "run_pipeline") as run_pipeline:
            result = pipeline_cli.main(
                [
                    "run",
                    "library/story",
                    "--force-stage",
                    "illustrate",
                    "--force-stage",
                    "render",
                ]
            )

        self.assertEqual(0, result)
        self.assertEqual(["illustrate", "render"], run_pipeline.call_args.kwargs["force_stage"])

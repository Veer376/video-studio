"""Exercise a realistic graph size without depending on private production data."""
import json
import tempfile
import unittest
from pathlib import Path

from test_visual_production import FakeImageProvider, make_project
from scripts.production.anchors import AnchorRegistry
from scripts.production.manifest import ManifestStore
from scripts.production.planner import build_plan
from scripts.production.runner import ProductionRunner, ProductionSettings, select_assets


class LargeGraphTests(unittest.TestCase):
    def test_128_scenes_207_assets_complete_then_reuse_without_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp))
            scenes = []
            for index in range(128):
                scenes.append({
                    "id": f"scene-{index + 1:03d}", "text": "Sample narration.",
                    "image_prompt": f"Simple illustrative state {index + 1}.",
                    "continuation_image_prompts": ["A later state."] if index < 79 else [],
                    "subjects": [], "location_id": None,
                    "reference_scene_id": f"scene-{index:03d}" if index else None,
                    "duration": 4.,
                })
            (project / "scenes.json").write_text(json.dumps({"version": 1, "scenes": scenes}))
            plan = build_plan(project)
            provider = FakeImageProvider()
            runner = ProductionRunner(plan=plan,
                manifest=ManifestStore(project / "production-manifest.json", project),
                anchors=AnchorRegistry(project / "production-anchors.json"),
                settings=ProductionSettings(), image_provider=provider)
            selected = select_assets(plan, phase="images")
            first = runner.run(selected, phase="images")
            self.assertEqual(len(first.completed), 207)
            self.assertEqual(len(provider.calls), 207)
            second = runner.run(selected, phase="images")
            self.assertEqual(len(second.skipped), 207)
            self.assertEqual(len(provider.calls), 207)

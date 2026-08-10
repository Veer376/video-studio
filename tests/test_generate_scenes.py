from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from generate_scenes import compile_scene, scene_first_frame_path, scene_output_path


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


if __name__ == "__main__":
    unittest.main()

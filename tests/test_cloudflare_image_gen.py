from __future__ import annotations

import io
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PIL import Image

from studio.core import paths as studio_paths
from studio.images import cloudflare_image_gen as image_gen


def image_bytes(*, size: tuple[int, int], image_format: str = "JPEG") -> bytes:
    output = io.BytesIO()
    Image.new("RGB", size, (40, 80, 120)).save(output, format=image_format)
    return output.getvalue()


def write_project(project_dir: Path, scenes: list[dict]) -> None:
    project_dir.mkdir()
    character_dir = project_dir / "assets" / "characters"
    character_dir.mkdir(parents=True)
    (character_dir / "hero.png").write_bytes(
        image_bytes(size=(32, 32), image_format="PNG")
    )
    (project_dir / "session.json").write_text(
        json.dumps(
            {
                "session": {"status": "storyboard_complete"},
                "visual": {
                    "aspect_ratio": "16:9",
                    "style_id": "oil_painting",
                    "style_prompt": "painted style",
                },
            }
        ),
        encoding="utf-8",
    )
    (project_dir / "scenes.json").write_text(
        json.dumps(
            {
                "characters": {
                    "hero": {
                        "canonical_name": "Hero",
                        "prompt": "a hero in a blue robe",
                        "image_path": "assets/characters/hero.png",
                    }
                },
                "scenes": scenes,
            }
        ),
        encoding="utf-8",
    )


class CloudflareImageGenTests(unittest.TestCase):
    def test_style_prompt_comes_from_session(self) -> None:
        style = image_gen.resolve_style_prompt(
            {
                "visual": {
                    "style_id": "oil_painting",
                    "style_prompt": "approved session style",
                }
            },
            {"visual_style": "stale copied style"},
        )

        self.assertEqual("approved session style", style)

    def test_missing_style_prompt_fails_without_default(self) -> None:
        with self.assertRaisesRegex(ValueError, "run orchestrate-visuals"):
            image_gen.resolve_style_prompt(
                {"visual": {"aspect_ratio": "9:16"}},
                {"scenes": []},
            )

    def test_legacy_scene_visual_style_still_resumes(self) -> None:
        self.assertEqual(
            "legacy style",
            image_gen.resolve_style_prompt(
                {"visual": {"aspect_ratio": "9:16"}},
                {"visual_style": "legacy style"},
            ),
        )

    def test_prepare_reference_image_is_real_png_under_512(self) -> None:
        with TemporaryDirectory() as tmp:
            source = Path(tmp) / "scene-001.png"
            source.write_bytes(image_bytes(size=(1920, 1072), image_format="JPEG"))

            prepared = image_gen.prepare_reference_image(source)

        self.assertTrue(prepared.startswith(b"\x89PNG\r\n\x1a\n"))
        with Image.open(io.BytesIO(prepared)) as image:
            self.assertEqual("PNG", image.format)
            self.assertLess(max(image.size), 512)
    def test_flux_references_use_all_official_multipart_fields(self) -> None:
        with TemporaryDirectory() as tmp:
            references = []
            for index in range(4):
                reference = Path(tmp) / f"reference-{index}.png"
                reference.write_bytes(image_bytes(size=(1072, 1920)))
                references.append(image_gen.ReferenceImage(reference, f"role {index}"))
            output = Path(tmp) / "scene-002.png"
            captured: dict[str, object] = {}

            class Response:
                headers = {"Content-Type": "image/jpeg"}

                def __enter__(self):
                    return self

                def __exit__(self, *_args):
                    return False

                def read(self) -> bytes:
                    return image_bytes(size=(64, 64))

            def fake_urlopen(request, **_kwargs):
                captured["body"] = request.data
                captured["content_type"] = request.headers["Content-type"]
                return Response()

            with patch.object(image_gen.urllib.request, "urlopen", side_effect=fake_urlopen):
                image_gen.generate_image(
                    credentials=[("account", "token")],
                    model="@cf/black-forest-labs/flux-2-klein-4b",
                    prompt="Hero runs through rain",
                    width=1080,
                    height=1920,
                    out_path=output,
                    reference_images=references,
                )

            body = captured["body"]
            self.assertIsInstance(body, bytes)
            for index in range(4):
                self.assertIn(f'name="input_image_{index}"'.encode(), body)
                self.assertIn(f"input image {index} is role {index}".encode(), body)
            self.assertNotIn(b'name="image"', body)
            self.assertNotIn(b'name="strength"', body)
            self.assertTrue(
                str(captured["content_type"]).startswith("multipart/form-data; boundary=")
            )
            with Image.open(output) as image:
                self.assertEqual("PNG", image.format)

    def test_source_identity_instruction_drops_source_medium_and_composition(self) -> None:
        instruction = image_gen.reference_instruction(
            [image_gen.ReferenceImage(Path("source.jpg"), "source identity of Hero")]
        )
        self.assertIn("identity evidence only", instruction)
        self.assertIn("do not preserve its medium", instruction)
    def test_clean_run_waits_for_reference_before_dependent_scene(self) -> None:
        with TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            scenes = [
                {
                    "id": "scene-001",
                    "text": "Hero enters.",
                    "image_prompt": "Hero enters a stone room",
                    "referenced_characters": ["hero"],
                    "reference_scene_id": None,
                    "image_path": None,
                },
                {
                    "id": "scene-002",
                    "text": "Hero sits.",
                    "image_prompt": "Hero sits in the same stone room",
                    "referenced_characters": ["hero"],
                    "reference_scene_id": "scene-001",
                    "image_path": None,
                },
                {
                    "id": "scene-003",
                    "text": "A river flows.",
                    "image_prompt": "A river flows between rocks",
                    "referenced_characters": [],
                    "reference_scene_id": None,
                    "image_path": None,
                },
            ]
            write_project(project, scenes)
            calls: list[tuple[str, str | None, bool]] = []

            def fake_generate_image(**kwargs) -> None:
                out_path: Path = kwargs["out_path"]
                references: list[image_gen.ReferenceImage] = kwargs["reference_images"]
                scene_reference = next(
                    (reference for reference in references if "previous scene" in reference.role),
                    None,
                )
                calls.append(
                    (
                        out_path.stem,
                        scene_reference.path.stem if scene_reference else None,
                        bool(scene_reference and scene_reference.path.exists()),
                    )
                )
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(image_bytes(size=(32, 32), image_format="PNG"))

            argv = [
                "cloudflare_image_gen.py",
                "--project-dir",
                str(project),
                "--concurrency",
                "3",
            ]
            with (
                patch.object(image_gen, "load_env"),
                patch.object(
                    image_gen,
                    "load_cloudflare_credentials",
                    return_value=[("a", "t")],
                ),
                patch.object(
                    image_gen,
                    "generate_image",
                    side_effect=fake_generate_image,
                ),
                patch.object(sys, "argv", argv),
            ):
                image_gen.main()

            call_by_scene = {
                scene_id: (ref_id, existed) for scene_id, ref_id, existed in calls
            }
            self.assertEqual((None, False), call_by_scene["scene-001"])
            self.assertEqual((None, False), call_by_scene["scene-003"])
            self.assertEqual(("scene-001", True), call_by_scene["scene-002"])
            self.assertGreater(
                calls.index(("scene-002", "scene-001", True)),
                calls.index(("scene-001", None, False)),
            )
    def test_reference_graph_rejects_forward_reference(self) -> None:
        scenes = [
            {"id": "scene-001", "reference_scene_id": "scene-002"},
            {"id": "scene-002", "reference_scene_id": None},
        ]
        with self.assertRaisesRegex(ValueError, "must reference an earlier scene"):
            image_gen.validate_reference_graph(scenes)

    def test_force_run_does_not_feed_stale_reference_after_parent_failure(self) -> None:
        with TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            scenes = [
                {
                    "id": "scene-001",
                    "text": "Hero enters.",
                    "image_prompt": "Hero enters a stone room",
                    "referenced_characters": ["hero"],
                    "reference_scene_id": None,
                    "image_path": "images/scene-001.png",
                },
                {
                    "id": "scene-002",
                    "text": "Hero sits.",
                    "image_prompt": "Hero sits in the same stone room",
                    "referenced_characters": ["hero"],
                    "reference_scene_id": "scene-001",
                    "image_path": "images/scene-002.png",
                },
            ]
            write_project(project, scenes)
            images = project / "images"
            images.mkdir()
            (images / "scene-001.png").write_bytes(
                image_bytes(size=(32, 32), image_format="PNG")
            )
            (images / "scene-002.png").write_bytes(
                image_bytes(size=(32, 32), image_format="PNG")
            )
            called: list[str] = []

            def fail_parent(**kwargs) -> None:
                scene_id = kwargs["out_path"].stem
                called.append(scene_id)
                if scene_id == "scene-001":
                    raise RuntimeError("provider failure")
                self.fail("dependent scene must not run after its forced reference fails")

            argv = [
                "cloudflare_image_gen.py",
                "--project-dir",
                str(project),
                "--phase",
                "scenes",
                "--force",
            ]
            with (
                patch.object(image_gen, "load_env"),
                patch.object(
                    image_gen,
                    "load_cloudflare_credentials",
                    return_value=[("a", "t")],
                ),
                patch.object(
                    image_gen,
                    "generate_image",
                    side_effect=fail_parent,
                ),
                patch.object(sys, "argv", argv),
                self.assertRaises(SystemExit),
            ):
                image_gen.main()

            self.assertEqual(["scene-001"], called)

    def test_non_flux_model_rejects_reference_instead_of_silently_ignoring_it(self) -> None:
        with TemporaryDirectory() as tmp:
            reference = Path(tmp) / "scene-001.png"
            reference.write_bytes(image_bytes(size=(32, 32), image_format="PNG"))
            with self.assertRaisesRegex(ValueError, "reference images are not configured"):
                image_gen.generate_image(
                    credentials=[("account", "token")],
                    model="@cf/black-forest-labs/flux-1-schnell",
                    prompt="Hero runs",
                    width=512,
                    height=512,
                    out_path=Path(tmp) / "scene-002.png",
                    reference_images=[image_gen.ReferenceImage(reference, "continuity")],
                )

    def test_prompt_assembly_strips_legacy_style_and_appends_character_once(self) -> None:
        prompt = image_gen.assemble_scene_prompt(
            {
                "id": "scene-001",
                "image_prompt": "painted style, Hero opens the door",
                "referenced_characters": ["hero"],
            },
            {"hero": {"canonical_name": "Hero", "prompt": "a hero in a blue robe"}},
            "painted style",
        )
        self.assertEqual(1, prompt.count("painted style"))
        self.assertEqual(1, prompt.count("a hero in a blue robe"))

    def test_reference_budget_prefers_prompt_visible_characters(self) -> None:
        with TemporaryDirectory() as tmp:
            project = Path(tmp)
            characters = {}
            for key in ("background", "hero", "villain", "ally"):
                path = project / "assets" / "characters" / f"{key}.png"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(image_bytes(size=(32, 32), image_format="PNG"))
                characters[key] = {
                    "canonical_name": key.title(),
                    "prompt": f"the {key}",
                    "image_path": f"assets/characters/{key}.png",
                }
            previous = project / "images" / "scene-001.png"
            previous.parent.mkdir()
            previous.write_bytes(image_bytes(size=(32, 32), image_format="PNG"))
            scene = {
                "id": "scene-002",
                "image_prompt": "Villain grabs Ally while Hero intervenes",
                "referenced_characters": ["background", "hero", "villain", "ally"],
                "reference_scene_id": "scene-001",
            }

            references = image_gen.scene_reference_images(project, scene, characters)

        self.assertEqual(4, len(references))
        self.assertIn("previous scene", references[0].role)
        self.assertEqual(
            ["canonical appearance of Villain", "canonical appearance of Ally", "canonical appearance of Hero"],
            [reference.role for reference in references[1:]],
        )

    def test_character_phase_persists_default_path_and_resumes(self) -> None:
        with TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            write_project(
                project,
                [
                    {
                        "id": "scene-001",
                        "text": "Hero enters.",
                        "image_prompt": "Hero enters",
                        "referenced_characters": ["hero"],
                        "reference_scene_id": None,
                        "image_path": None,
                    }
                ],
            )
            manifest_path = project / "scenes.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["characters"]["hero"].pop("image_path")
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            (project / "assets" / "characters" / "hero.png").unlink()
            generated: list[str] = []

            def fake_generate_image(**kwargs) -> None:
                out_path: Path = kwargs["out_path"]
                generated.append(str(out_path.resolve().relative_to(project.resolve())))
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(image_bytes(size=(32, 32), image_format="PNG"))

            argv = [
                "cloudflare_image_gen.py",
                "--project-dir",
                str(project),
                "--phase",
                "characters",
            ]
            for _ in range(2):
                with (
                    patch.object(image_gen, "load_env"),
                    patch.object(image_gen, "load_cloudflare_credentials", return_value=[("a", "t")]),
                    patch.object(image_gen, "generate_image", side_effect=fake_generate_image),
                    patch.object(sys, "argv", argv),
                ):
                    image_gen.main()

            updated = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(["assets/characters/hero.png"], generated)
        self.assertEqual(
            "assets/characters/hero.png",
            updated["characters"]["hero"]["image_path"],
        )

    def test_rejects_more_than_four_references(self) -> None:
        with TemporaryDirectory() as tmp:
            references = []
            for index in range(5):
                path = Path(tmp) / f"{index}.png"
                path.write_bytes(image_bytes(size=(32, 32), image_format="PNG"))
                references.append(image_gen.ReferenceImage(path, str(index)))
            with self.assertRaisesRegex(ValueError, "at most 4"):
                image_gen.generate_image(
                    credentials=[("a", "t")],
                    model="@cf/black-forest-labs/flux-2-klein-4b",
                    prompt="scene",
                    width=512,
                    height=512,
                    out_path=Path(tmp) / "out.png",
                    reference_images=references,
                )

    def test_shared_root_asset_with_null_prompt_is_reused_without_generation(self) -> None:
        with TemporaryDirectory() as tmp:
            repository = Path(tmp) / "repository"
            project = repository / "library" / "story"
            shared = repository / "assets" / "characters" / "hero.png"
            shared.parent.mkdir(parents=True)
            shared.write_bytes(image_bytes(size=(32, 32), image_format="PNG"))
            project.mkdir(parents=True)
            characters = {
                "hero": {
                    "canonical_name": "Hero",
                    "prompt": None,
                    "image_path": "root:assets/characters/hero.png",
                }
            }

            with patch.object(studio_paths, "project_root", return_value=repository):
                tasks = image_gen.plan_character_tasks(project, characters, force=False)
                prompt = image_gen.assemble_scene_prompt(
                    {
                        "id": "scene-001",
                        "image_prompt": "Hero enters the room",
                        "referenced_characters": ["hero"],
                    },
                    characters,
                    "painted style",
                )
                references = image_gen.scene_reference_images(
                    project,
                    {
                        "id": "scene-001",
                        "image_prompt": "Hero enters the room",
                        "referenced_characters": ["hero"],
                    },
                    characters,
                )

        self.assertEqual([], tasks)
        self.assertNotIn("Hero:", prompt)
        self.assertEqual(shared.resolve(), references[0].path)

    def test_shared_root_asset_with_prompt_adapts_once_and_rewrites_manifest(self) -> None:
        with TemporaryDirectory() as tmp:
            repository = Path(tmp) / "repository"
            project = repository / "library" / "story"
            shared = repository / "assets" / "characters" / "hero-photo.png"
            shared.parent.mkdir(parents=True)
            shared.write_bytes(image_bytes(size=(64, 32), image_format="PNG"))
            project.mkdir(parents=True)
            (project / "session.json").write_text(
                json.dumps(
                    {
                        "session": {"status": "storyboard_complete"},
                        "visual": {
                            "aspect_ratio": "9:16",
                            "style_id": "oil_painting",
                            "style_prompt": "painted style",
                        },
                    }
                ),
                encoding="utf-8",
            )
            manifest_path = project / "scenes.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "characters": {
                            "hero": {
                                "canonical_name": "Hero",
                                "prompt": "a hero in a blue robe",
                                "image_path": "root:assets/characters/hero-photo.png",
                            }
                        },
                        "scenes": [
                            {
                                "id": "scene-001",
                                "text": "Hero enters.",
                                "image_prompt": "Hero enters",
                                "referenced_characters": ["hero"],
                                "reference_scene_id": None,
                                "image_path": None,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            calls: list[tuple[str, list[Path]]] = []

            def fake_generate_image(**kwargs) -> None:
                out_path: Path = kwargs["out_path"]
                references: list[image_gen.ReferenceImage] = kwargs["reference_images"]
                calls.append(
                    (
                        str(out_path.resolve().relative_to(project.resolve())),
                        [r.path for r in references],
                    )
                )
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(image_bytes(size=(32, 64), image_format="PNG"))

            argv = [
                "cloudflare_image_gen.py",
                "--project-dir",
                str(project),
                "--phase",
                "characters",
            ]
            for _ in range(2):
                with (
                    patch.object(studio_paths, "project_root", return_value=repository),
                    patch.object(image_gen, "load_env"),
                    patch.object(
                        image_gen,
                        "load_cloudflare_credentials",
                        return_value=[("a", "t")],
                    ),
                    patch.object(
                        image_gen,
                        "generate_image",
                        side_effect=fake_generate_image,
                    ),
                    patch.object(sys, "argv", argv),
                ):
                    image_gen.main()

            updated = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(
            [("assets/characters/hero.png", [shared.resolve()])],
            calls,
        )
        self.assertEqual(
            "assets/characters/hero.png",
            updated["characters"]["hero"]["image_path"],
        )

    def test_reference_overflow_rejects_null_prompt_character(self) -> None:
        with TemporaryDirectory() as tmp:
            project = Path(tmp)
            characters = {}
            for key in ("one", "two", "three", "four"):
                path = project / "assets" / "characters" / f"{key}.png"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(image_bytes(size=(32, 32), image_format="PNG"))
                characters[key] = {
                    "canonical_name": key.title(),
                    "prompt": None if key == "four" else f"character {key}",
                    "image_path": f"assets/characters/{key}.png",
                }
            previous = project / "images" / "scene-001.png"
            previous.parent.mkdir()
            previous.write_bytes(image_bytes(size=(32, 32), image_format="PNG"))
            scene = {
                "id": "scene-002",
                "image_prompt": "One meets Two while Three and Four watch",
                "referenced_characters": ["one", "two", "three", "four"],
                "reference_scene_id": "scene-001",
            }

            with self.assertRaisesRegex(ValueError, "add prompt fallbacks for: four"):
                image_gen.scene_reference_images(project, scene, characters)

    def test_root_locator_cannot_escape_shared_assets(self) -> None:
        with TemporaryDirectory() as tmp:
            repository = Path(tmp) / "repository"
            project = repository / "library" / "story"
            project.mkdir(parents=True)
            character = {
                "canonical_name": "Hero",
                "prompt": None,
                "image_path": "root:../secret.png",
            }
            with (
                patch.object(studio_paths, "project_root", return_value=repository),
                self.assertRaisesRegex(ValueError, "must stay under root:assets"),
            ):
                image_gen.character_asset_path(project, "hero", character)

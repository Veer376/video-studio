import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import Mock, patch

from PIL import Image

from studio.images import illustrate
from studio.images.providers import cloudflare, google


def png_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (8, 8), "red").save(output, format="PNG")
    return output.getvalue()


class GoogleImageGenerationTests(unittest.TestCase):
    def test_standalone_cli_refuses_existing_output_before_auth(self) -> None:
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "image.png"
            output.write_bytes(png_bytes())
            with (
                patch.object(google, "create_client") as create_client,
                self.assertRaises(SystemExit),
            ):
                google.main(
                    [
                        "--model",
                        "gemini-3.1-flash-image",
                        "--prompt",
                        "a quiet forest",
                        "--output",
                        str(output),
                    ]
                )
        create_client.assert_not_called()

    def test_generates_with_ordered_references_and_image_config(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "first.png"
            second = root / "second.png"
            first.write_bytes(png_bytes())
            second.write_bytes(png_bytes())
            output = root / "result.png"
            response = SimpleNamespace(
                candidates=[
                    SimpleNamespace(
                        content=SimpleNamespace(
                            parts=[
                                SimpleNamespace(
                                    thought=False,
                                    inline_data=SimpleNamespace(data=png_bytes()),
                                )
                            ]
                        )
                    )
                ]
            )
            client = SimpleNamespace(
                models=SimpleNamespace(generate_content=Mock(return_value=response))
            )
            references = [
                SimpleNamespace(path=first, role="previous scene"),
                SimpleNamespace(path=second, role="canonical hero"),
            ]

            google.generate_image(
                client=client,
                model="gemini-3.1-flash-image",
                prompt="Hero enters",
                aspect_ratio="9:16",
                out_path=output,
                reference_images=references,
            )

            call = client.models.generate_content.call_args
            parts = call.kwargs["contents"][0].parts
            prompt = parts[-1].text
            config = call.kwargs["config"]

            self.assertTrue(output.exists())

        self.assertLess(prompt.index("input image 0 is previous scene"), prompt.index("input image 1 is canonical hero"))
        self.assertEqual("9:16", config.image_config.aspect_ratio)
        self.assertEqual("2K", config.image_config.image_size)

    def test_no_final_image_fails(self) -> None:
        response = SimpleNamespace(
            candidates=[SimpleNamespace(content=SimpleNamespace(parts=[]))]
        )
        with self.assertRaisesRegex(RuntimeError, "no final image"):
            google._final_image_bytes(response)

    def test_project_orchestration_dispatches_google_with_character_reference(self) -> None:
        with TemporaryDirectory() as tmp:
            project = Path(tmp)
            character_path = project / "assets" / "characters" / "hero.png"
            character_path.parent.mkdir(parents=True)
            character_path.write_bytes(png_bytes())
            (project / "session.json").write_text(
                json.dumps(
                    {
                        "session": {"status": "storyboard_complete"},
                        "visual": {
                            "aspect_ratio": "9:16",
                            "style_id": "oil_painting",
                            "style_prompt": "textured oil painting",
                        },
                    }
                ),
                encoding="utf-8",
            )
            scenes_path = project / "scenes.json"
            scenes_path.write_text(
                json.dumps(
                    {
                        "characters": {
                            "hero": {
                                "canonical_name": "Hero",
                                "prompt": "a hero in a blue robe",
                                "image_path": "assets/characters/hero.png",
                            }
                        },
                        "scenes": [
                            {
                                "id": "scene-001",
                                "text": "Hero enters.",
                                "image_prompt": "Hero enters a forest",
                                "referenced_characters": ["hero"],
                                "reference_scene_id": None,
                                "image_path": None,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            calls = []

            def fake_google_generate(**kwargs):
                calls.append(kwargs)
                kwargs["out_path"].parent.mkdir(parents=True, exist_ok=True)
                kwargs["out_path"].write_bytes(png_bytes())

            argv = [
                "illustrate.py",
                "--project-dir",
                str(project),
                "--provider",
                "google",
                "--model",
                "gemini-3.1-flash-image",
            ]
            with (
                patch.object(illustrate, "load_env"),
                patch.object(cloudflare, "load_credentials", return_value=[]),
                patch.object(google, "create_client", return_value=object()),
                patch.object(google, "generate_image", side_effect=fake_google_generate),
                patch.object(sys, "argv", argv),
            ):
                illustrate.main()

        self.assertEqual(1, len(calls))
        self.assertEqual("9:16", calls[0]["aspect_ratio"])
        self.assertEqual("canonical appearance of Hero", calls[0]["reference_images"][0].role)

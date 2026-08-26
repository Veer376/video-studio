from __future__ import annotations

import io
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PIL import Image

from studio.images import illustrate
from studio.images.providers import cloudflare, flow


def png_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (16, 16), "blue").save(output, format="PNG")
    return output.getvalue()


class FlowImageGenerationTests(unittest.TestCase):
    def setUp(self) -> None:
        flow._REFERENCE_MEDIA_CACHE.clear()

    def test_model_aliases_map_to_flow_backend_ids(self) -> None:
        self.assertEqual("harbor_seal", flow.normalize_model("lite"))
        self.assertEqual("harbor_seal", flow.normalize_model("harbor_seal"))
        self.assertEqual("gem_pix_2", flow.normalize_model("pro"))

    def test_require_ready_validates_extension_and_key(self) -> None:
        with patch.object(
            flow,
            "_json_request",
            return_value={"extension_connected": True, "has_flow_key": True},
        ) as request:
            health = flow.require_ready("http://flow.test")
        self.assertTrue(health["extension_connected"])
        request.assert_called_once_with("http://flow.test/health", timeout=8)

    def test_generate_uses_ordered_reference_media_ids_and_landscape_size(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            previous = root / "previous.png"
            hero = root / "hero.png"
            previous.write_bytes(png_bytes())
            hero.write_bytes(png_bytes())
            output = root / "result.png"
            references = [
                illustrate.ReferenceImage(previous, "previous scene scene-001 for visual continuity"),
                illustrate.ReferenceImage(hero, "canonical appearance of Hero"),
            ]
            requests: list[tuple[str, dict | None]] = []

            def fake_json_request(url, *, body=None, timeout=30):
                requests.append((url, body))
                if url.endswith("/v1/upload"):
                    upload_number = sum(1 for item_url, _ in requests if item_url.endswith("/v1/upload"))
                    return {"media_id": f"media-{upload_number}"}
                if url.endswith("/v1/images/generations"):
                    return {"data": [{"url": "https://example.test/generated.jpg"}]}
                raise AssertionError(url)

            def fake_download(_url: str, out_path: Path) -> None:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(png_bytes())

            with (
                patch.object(flow, "_json_request", side_effect=fake_json_request),
                patch.object(flow, "_download_image_as_png", side_effect=fake_download),
            ):
                flow.generate_image(
                    model="lite",
                    prompt="Hero lowers his hand slightly",
                    aspect_ratio="16:9",
                    out_path=output,
                    reference_images=references,
                    base_url="http://flow.test",
                )

            generation_body = next(
                body for url, body in requests if url.endswith("/v1/images/generations")
            )
            self.assertEqual("harbor_seal", generation_body["model"])
            self.assertEqual("1792x1024", generation_body["size"])
            self.assertEqual(["media-1", "media-2"], generation_body["ref_media_ids"])
            self.assertIn(
                "reference image 0 is previous scene scene-001 for visual continuity",
                generation_body["prompt"],
            )
            self.assertIn(
                "reference image 1 is canonical appearance of Hero",
                generation_body["prompt"],
            )
            self.assertTrue(output.exists())

    def test_reference_upload_cache_is_verified_before_reuse(self) -> None:
        with TemporaryDirectory() as tmp:
            reference = Path(tmp) / "hero.png"
            reference.write_bytes(png_bytes())
            upload_calls = 0
            history_calls = 0

            def fake_json_request(url, *, body=None, timeout=30):
                nonlocal upload_calls, history_calls
                if url.endswith("/v1/upload"):
                    upload_calls += 1
                    return {"media_id": "hero-media"}
                if url.endswith("/v1/history"):
                    history_calls += 1
                    return {"history": [{"media_id": "hero-media"}]}
                raise AssertionError(url)

            with patch.object(flow, "_json_request", side_effect=fake_json_request):
                first = flow.upload_reference(reference, base_url="http://flow.test")
                second = flow.upload_reference(reference, base_url="http://flow.test")

            self.assertEqual("hero-media", first)
            self.assertEqual(first, second)
            self.assertEqual(1, upload_calls)
            self.assertEqual(1, history_calls)

    def test_project_orchestration_dispatches_flow_with_character_reference(self) -> None:
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
                            "aspect_ratio": "16:9",
                            "style_id": "cinematic_realism",
                            "style_prompt": "cinematic realistic still",
                        },
                    }
                ),
                encoding="utf-8",
            )
            (project / "scenes.json").write_text(
                json.dumps(
                    {
                        "characters": {
                            "hero": {
                                "canonical_name": "Hero",
                                "prompt": "young Indian man in a muted blue shirt",
                                "image_path": "assets/characters/hero.png",
                            }
                        },
                        "scenes": [
                            {
                                "id": "scene-001",
                                "text": "Hero pauses.",
                                "image_prompt": "Hero pauses with one hand above his phone",
                                "referenced_characters": ["hero"],
                                "reference_scene_id": None,
                                "image_path": None,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            calls: list[dict] = []

            def fake_flow_generate(**kwargs):
                calls.append(kwargs)
                kwargs["out_path"].parent.mkdir(parents=True, exist_ok=True)
                kwargs["out_path"].write_bytes(png_bytes())

            argv = [
                "illustrate.py",
                "--project-dir",
                str(project),
                "--provider",
                "flow",
                "--model",
                "lite",
            ]
            with (
                patch.object(illustrate, "load_env"),
                patch.object(cloudflare, "load_credentials", return_value=[]),
                patch.object(flow, "require_ready", return_value={}),
                patch.object(flow, "generate_image", side_effect=fake_flow_generate),
                patch.object(sys, "argv", argv),
            ):
                illustrate.main()

        self.assertEqual(1, len(calls))
        self.assertEqual("harbor_seal", calls[0]["model"])
        self.assertEqual("16:9", calls[0]["aspect_ratio"])
        self.assertEqual(
            "canonical appearance of Hero",
            calls[0]["reference_images"][0].role,
        )


if __name__ == "__main__":
    unittest.main()

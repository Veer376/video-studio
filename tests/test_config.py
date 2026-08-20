import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from studio.core.config import load_production_config


class ProductionConfigTests(unittest.TestCase):
    def test_invocation_overrides_repository_config(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "production": {
                            "image_provider": "cloudflare",
                            "image_model": "cf-model",
                            "subtitles": True,
                            "zoom": True,
                        }
                    }
                ),
                encoding="utf-8",
            )
            config = load_production_config(
                provider="google",
                model="gemini-3.1-flash-image",
                subtitles=False,
                config_path=path,
            )

        self.assertEqual("google", config.image_provider)
        self.assertEqual("gemini-3.1-flash-image", config.image_model)
        self.assertFalse(config.subtitles)
        self.assertTrue(config.zoom)

    def test_session_production_model_and_provider_are_ignored(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "production": {
                            "image_provider": "cloudflare",
                            "image_model": "configured-model",
                            "subtitles": False,
                            "zoom": True,
                        }
                    }
                ),
                encoding="utf-8",
            )
            config = load_production_config(
                {
                    "production": {
                        "image_provider": "google",
                        "image_model": "session-model",
                        "subtitles": True,
                    }
                },
                config_path=path,
            )

        self.assertEqual("cloudflare", config.image_provider)
        self.assertEqual("configured-model", config.image_model)
        self.assertFalse(config.subtitles)

    def test_invalid_boolean_is_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "production": {
                            "image_provider": "cloudflare",
                            "image_model": "model",
                            "subtitles": "yes",
                        }
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "must be true or false"):
                load_production_config(config_path=path)

    def test_provider_change_requires_explicit_model(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "production": {
                            "image_provider": "cloudflare",
                            "image_model": "configured-model",
                        }
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "requires an explicit image model"):
                load_production_config(provider="google", config_path=path)

    def test_short_overrides_base_render_settings(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "production": {
                            "image_provider": "cloudflare",
                            "image_model": "model",
                            "subtitles": False,
                            "zoom": True,
                            "short": {"subtitles": True, "zoom": False},
                        }
                    }
                ),
                encoding="utf-8",
            )
            short = load_production_config(
                {
                    "visual": {"aspect_ratio": "9:16"},
                    "brief": {"target_duration_seconds": 90},
                },
                config_path=path,
            )
            long = load_production_config(
                {
                    "visual": {"aspect_ratio": "16:9"},
                    "brief": {"target_duration_seconds": 600},
                },
                config_path=path,
            )

        self.assertTrue(short.subtitles)
        self.assertFalse(short.zoom)
        self.assertFalse(long.subtitles)
        self.assertTrue(long.zoom)

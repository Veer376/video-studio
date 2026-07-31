import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from story_video.audio import generate_groq_audio, generate_sarvam_preview, pace_narration_audio
from story_video.manifest import parse_manifest


class FakeResponse:
    payload = b"fake-wav"

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.payload


class GroqAudioTests(unittest.TestCase):
    def test_groq_generation_writes_deterministic_scene_file(self):
        manifest = parse_manifest(
            {
                "project": {"title": "x", "language": "hi-IN", "aspect_ratio": "16:9", "resolution": "320x180", "fps": 15},
                "voice": {
                    "provider": "groq_tts",
                    "model": "canopylabs/orpheus-v1-english",
                    "voice": "troy",
                    "response_format": "wav",
                    "sample_rate": 44100,
                    "speed": 1.0,
                },
                "scenes": [
                    {
                        "id": "scene-001",
                        "narration": "नमस्ते",
                        "image_prompt": "x",
                        "image_path": "generated/images/scene-001.png",
                        "audio_path": None,
                    }
                ],
            }
        )
        with TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            with patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}):
                with patch("story_video.audio.urllib.request.urlopen", return_value=FakeResponse()) as mocked:
                    with patch("story_video.audio._ssl_context", return_value=None):
                        with patch("story_video.audio.ffmpeg.probe_duration", return_value=1.0):
                            generate_groq_audio(manifest, base_dir)
            self.assertEqual(manifest.scenes[0].audio_path, "generated/audio/scene-001.wav")
            self.assertEqual((base_dir / "generated/audio/scene-001.wav").read_bytes(), b"fake-wav")
            request = mocked.call_args.args[0]
            self.assertEqual(request.headers["Authorization"], "Bearer test-key")

    def test_groq_generation_reuses_existing_audio_without_force(self):
        manifest = parse_manifest(
            {
                "project": {"title": "x", "language": "hi-IN", "aspect_ratio": "16:9", "resolution": "320x180", "fps": 15},
                "voice": {"provider": "groq_tts", "voice": "troy"},
                "scenes": [
                    {
                        "id": "scene-001",
                        "narration": "नमस्ते",
                        "image_prompt": "x",
                        "image_path": "generated/images/scene-001.png",
                        "audio_path": "generated/audio/scene-001.wav",
                    }
                ],
            }
        )
        with TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            out = base_dir / "generated/audio/scene-001.wav"
            out.parent.mkdir(parents=True)
            out.write_bytes(b"existing")
            with patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}):
                with patch("story_video.audio.urllib.request.urlopen") as mocked:
                    generate_groq_audio(manifest, base_dir)
            mocked.assert_not_called()
            self.assertEqual(out.read_bytes(), b"existing")

    def test_groq_generation_resets_paced_manifest_path_to_raw_path(self):
        manifest = parse_manifest(
            {
                "project": {"title": "x", "language": "hi-IN", "aspect_ratio": "16:9", "resolution": "320x180", "fps": 15},
                "voice": {"provider": "groq_tts", "voice": "autumn", "response_format": "wav"},
                "scenes": [
                    {
                        "id": "scene-001",
                        "narration": "नमस्ते",
                        "image_prompt": "x",
                        "image_path": "generated/images/scene-001.png",
                        "audio_path": "generated/audio/paced/scene-001.wav",
                    }
                ],
            }
        )
        with TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            with patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}):
                with patch("story_video.audio.urllib.request.urlopen", return_value=FakeResponse()):
                    with patch("story_video.audio._ssl_context", return_value=None):
                        with patch("story_video.audio.ffmpeg.probe_duration", return_value=1.0):
                            generate_groq_audio(manifest, base_dir, force=True)
            self.assertEqual(manifest.scenes[0].audio_path, "generated/audio/scene-001.wav")
            self.assertTrue((base_dir / "generated/audio/scene-001.wav").exists())

    def test_sarvam_preview_decodes_base64_audio(self):
        manifest = parse_manifest(
            {
                "project": {"title": "x", "language": "hi-IN", "aspect_ratio": "16:9", "resolution": "320x180", "fps": 15},
                "voice": {"provider": "sarvam_tts", "model": "bulbul:v3", "voice": "shubh", "response_format": "wav"},
                "scenes": [
                    {
                        "id": "scene-001",
                        "narration": "नमस्ते",
                        "image_prompt": "x",
                        "image_path": "generated/images/scene-001.png",
                        "audio_path": None,
                    }
                ],
            }
        )
        response = FakeResponse()
        response.payload = b'{"audios":["ZmFrZS13YXY="]}'
        with TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            with patch.dict(os.environ, {"SARVAM_API_KEY": "test-key"}):
                with patch("story_video.audio.urllib.request.urlopen", return_value=response) as mocked:
                    with patch("story_video.audio._ssl_context", return_value=None):
                        with patch("story_video.audio.ffmpeg.probe_duration", return_value=1.0):
                            out_path = generate_sarvam_preview(manifest, base_dir, force=True)
            self.assertEqual(out_path.read_bytes(), b"fake-wav")
            request = mocked.call_args.args[0]
            self.assertEqual(request.headers["Api-subscription-key"], "test-key")

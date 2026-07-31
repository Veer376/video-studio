import unittest

from story_video.manifest import parse_manifest
from story_video.models import ManifestError


def minimal_manifest():
    return {
        "project": {"title": "x", "language": "hi-IN", "aspect_ratio": "16:9", "resolution": "1920x1080", "fps": 30},
        "voice": {"provider": "existing_audio"},
        "scenes": [
            {
                "id": "scene-001",
                "narration": "नमस्ते",
                "image_prompt": "placeholder",
                "image_path": "generated/images/scene-001.png",
                "audio_path": "generated/audio/scene-001.wav",
            }
        ],
    }


class ManifestTests(unittest.TestCase):
    def test_parse_manifest_accepts_minimal_valid_shape(self):
        manifest = parse_manifest(minimal_manifest())
        self.assertEqual(manifest.project.width_height, (1920, 1080))
        self.assertEqual(manifest.scenes[0].subtitle, "नमस्ते")

    def test_parse_manifest_rejects_duplicate_scene_ids(self):
        data = minimal_manifest()
        data["scenes"].append(dict(data["scenes"][0]))
        with self.assertRaisesRegex(ManifestError, "Duplicate scene id"):
            parse_manifest(data)

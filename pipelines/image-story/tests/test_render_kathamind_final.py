import json
import tempfile
import unittest
from pathlib import Path
from scripts.render_kathamind_final import (build_scene_slots, validate_word_ownership,
    resolve_all_media, build_phrase_captions, narration_path, RenderError)

PROJECT = Path(__file__).resolve().parents[1] / "examples/offline"

class RenderPlanTests(unittest.TestCase):
    def setUp(self):
        self.scenes = json.loads((PROJECT / "scenes.json").read_text())["scenes"]
        self.words = json.loads((PROJECT / "audio/timestamps.json").read_text())["words"]
        self.assets = json.loads((PROJECT / "production-manifest.json").read_text())["assets"]
    def test_slots_partition_narration(self):
        slots = build_scene_slots(self.scenes, 8.)
        self.assertEqual(sum(s.slot_duration for s in slots), 8.)
        self.assertEqual(slots[-1].slot_end, 8.)
    def test_words_partition_without_duplication(self):
        ownership = validate_word_ownership(self.scenes, self.words)
        self.assertEqual(sum(map(len, ownership.values())), len(self.words))
    def test_continuation_order(self):
        media = resolve_all_media(PROJECT, self.scenes, self.assets)
        self.assertEqual([p.name for p in media[0].paths], ["scene-001.png", "scene-001-c01.png"])
    def test_phrase_captions_preserve_words(self):
        captions = build_phrase_captions(self.words[:3], scene_start=0, scene_end=4)
        self.assertEqual(sum(c.word_count for c in captions), 3)
    def test_wav_narration_and_missing_input(self):
        self.assertEqual(narration_path(PROJECT).suffix, ".wav")
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(RenderError): narration_path(Path(t))

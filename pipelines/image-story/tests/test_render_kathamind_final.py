import json
import math
import unittest
from pathlib import Path

from scripts.render_kathamind_final import (
    build_phrase_captions,
    build_scene_slots,
    resolve_all_media,
    validate_word_ownership,
)


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "library" / "koi-tumhe-serious-nahi-leta"


class KathaMindRenderPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scenes = json.loads((PROJECT / "scenes.json").read_text(encoding="utf-8"))["scenes"]
        cls.timestamps = json.loads((PROJECT / "audio" / "timestamps.json").read_text(encoding="utf-8"))
        cls.words = cls.timestamps["words"]
        cls.assets = json.loads((PROJECT / "production-manifest.json").read_text(encoding="utf-8"))["assets"]

    def test_slots_preserve_full_narration_timeline_and_pauses(self):
        slots = build_scene_slots(self.scenes, float(self.timestamps["duration"]))
        self.assertEqual(128, len(slots))
        self.assertAlmostEqual(0.0, slots[0].slot_start, places=6)
        self.assertAlmostEqual(float(self.timestamps["duration"]), slots[-1].slot_end, places=6)
        self.assertAlmostEqual(
            float(self.timestamps["duration"]),
            sum(slot.slot_duration for slot in slots),
            places=5,
        )
        self.assertGreater(sum(slot.pause_duration for slot in slots), 66.0)

        # Render durations are derived from shared absolute frame boundaries,
        # so per-scene frame rounding cannot accumulate across 128 clips.
        fps = 24
        self.assertEqual(
            math.ceil(float(self.timestamps["duration"]) * fps),
            sum(round(slot.render_slot_duration(fps) * fps) for slot in slots),
        )

    def test_word_indices_partition_all_timestamp_words_and_match_time_assignment(self):
        ownership = validate_word_ownership(self.scenes, self.words)
        self.assertEqual(len(self.words), sum(len(items) for items in ownership.values()))
        self.assertEqual(0, self.scenes[0]["word_start"])
        self.assertEqual(len(self.words) - 1, self.scenes[-1]["word_end"])

    def test_manifest_media_prefers_generated_video_and_orders_continuations(self):
        media = resolve_all_media(PROJECT, self.scenes, self.assets)
        by_id = {item.scene_id: item for item in media}
        self.assertEqual("video", by_id["scene-004"].kind)
        self.assertEqual((PROJECT / "videos" / "scene-004.mp4",), by_id["scene-004"].paths)

        self.assertEqual("images", by_id["scene-002"].kind)
        self.assertEqual(
            (
                PROJECT / "images" / "scene-002.png",
                PROJECT / "images" / "scene-002-c01.png",
            ),
            by_id["scene-002"].paths,
        )

        self.assertEqual("images", by_id["scene-016"].kind)
        self.assertEqual(
            ["scene-016.png", "scene-016-c01.png", "scene-016-c02.png"],
            [path.name for path in by_id["scene-016"].paths],
        )

    def test_current_project_has_expected_generated_video_count(self):
        media = resolve_all_media(PROJECT, self.scenes, self.assets)
        self.assertEqual(12, sum(item.kind == "video" for item in media))

    def test_phrase_captioning_preserves_aligned_word_count(self):
        ownership = validate_word_ownership(self.scenes, self.words)
        for idx, scene in enumerate(self.scenes[:12]):
            captions = build_phrase_captions(
                ownership[idx],
                scene_start=float(scene["start_time"]),
                scene_end=float(scene["end_time"]),
            )
            self.assertEqual(len(ownership[idx]), sum(item.word_count for item in captions))
            self.assertTrue(all(1 <= item.word_count <= 6 for item in captions))
            self.assertTrue(all(item.relative_end > item.relative_start for item in captions))


if __name__ == "__main__":
    unittest.main()

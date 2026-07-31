import unittest

from story_video.subtitles import break_subtitle, format_srt_time


class SubtitleTests(unittest.TestCase):
    def test_format_srt_time(self):
        self.assertEqual(format_srt_time(65.432), "00:01:05,432")

    def test_break_subtitle_keeps_devanagari_text(self):
        text = "सही समय नहीं आया था पर सही कर्म शुरू हो चुका था"
        broken = break_subtitle(text, max_chars=24)
        self.assertIn("सही", broken)
        self.assertLessEqual(len(broken.splitlines()), 2)

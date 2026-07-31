import unittest

from story_video.audio import _atempo_chain
from story_video.renderer import motion_filter


class FFmpegCommandTests(unittest.TestCase):
    def test_motion_filter_constructs_zoom_expression(self):
        zoom, x_expr, y_expr = motion_filter("slow_zoom_in", 0.04, 120)
        self.assertIn("on*", zoom)
        self.assertIn("zoom", x_expr)
        self.assertIn("zoom", y_expr)

    def test_atempo_chain_keeps_filter_values_in_range(self):
        chain = _atempo_chain(0.25)
        self.assertEqual(chain[0], "atempo=0.5")
        self.assertEqual(chain[1], "atempo=0.500000")

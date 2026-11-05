import unittest

from audio.base import _atempo_chain
from renderer import motion_filter
from subtitles import subtitle_enable_expr


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

    def test_subtitle_enable_expression_is_end_exclusive(self):
        expr = subtitle_enable_expr(1.0, 2.5)
        self.assertEqual(expr, "gte(t,1.0000)*lt(t,2.5000)")
        self.assertNotIn("between", expr)

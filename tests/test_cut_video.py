"""Unit and integration tests for scripts/cut_video.py."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.cut_video import (
    CutError,
    build_ffmpeg_cmd,
    cut_video,
    get_media_info,
    parse_args,
    parse_range,
    parse_time,
    resolve_keep_segments,
)


class TestTimestampParsing(unittest.TestCase):
    """Test timestamp and range parsing logic."""

    def test_parse_time_numeric(self):
        self.assertAlmostEqual(parse_time(5), 5.0)
        self.assertAlmostEqual(parse_time("5"), 5.0)
        self.assertAlmostEqual(parse_time("5.5"), 5.5)
        self.assertAlmostEqual(parse_time("0.25"), 0.25)
        self.assertIsNone(parse_time(None))
        self.assertIsNone(parse_time(""))

    def test_parse_time_mm_ss(self):
        self.assertAlmostEqual(parse_time("01:23"), 83.0)
        self.assertAlmostEqual(parse_time("0:0.5"), 0.5)
        self.assertAlmostEqual(parse_time("02:30.5"), 150.5)

    def test_parse_time_hh_mm_ss(self):
        self.assertAlmostEqual(parse_time("01:00:00"), 3600.0)
        self.assertAlmostEqual(parse_time("00:01:30.5"), 90.5)

    def test_parse_time_invalid(self):
        with self.assertRaises(CutError):
            parse_time("invalid_timestamp")
        with self.assertRaises(CutError):
            parse_time("1:2:3:4")

    def test_parse_range(self):
        start, end, dur = parse_range("2.5:7.5")
        self.assertAlmostEqual(start, 2.5)
        self.assertAlmostEqual(end, 7.5)
        self.assertAlmostEqual(dur, 5.0)

        start, end, dur = parse_range(":5.0")
        self.assertAlmostEqual(start, 0.0)
        self.assertAlmostEqual(end, 5.0)

        start, end, dur = parse_range("3.0:")
        self.assertAlmostEqual(start, 3.0)
        self.assertIsNone(end)

        start, end, dur = parse_range("2.0+4.5")
        self.assertAlmostEqual(start, 2.0)
        self.assertAlmostEqual(end, 6.5)
        self.assertAlmostEqual(dur, 4.5)

        start, end, dur = parse_range("0-2.5")
        self.assertAlmostEqual(start, 0.0)
        self.assertAlmostEqual(end, 2.5)
        self.assertAlmostEqual(dur, 2.5)

        start, end, dur = parse_range("1.5-4.0")
        self.assertAlmostEqual(start, 1.5)
        self.assertAlmostEqual(end, 4.0)
        self.assertAlmostEqual(dur, 2.5)



class TestSegmentResolution(unittest.TestCase):
    """Test resolution of keep vs cut operations."""

    def test_cut_start(self):
        # Cut off first 2.5s from 10s video -> keep [2.5, 10.0]
        segs, desc = resolve_keep_segments(10.0, cut_start_sec=2.5)
        self.assertEqual(len(segs), 1)
        self.assertAlmostEqual(segs[0][0], 2.5)
        self.assertAlmostEqual(segs[0][1], 10.0)
        self.assertIn("CUT HEAD", desc)

    def test_cut_end(self):
        # Cut off last 2.0s from 10s video -> keep [0.0, 8.0]
        segs, desc = resolve_keep_segments(10.0, cut_end_sec=2.0)
        self.assertEqual(len(segs), 1)
        self.assertAlmostEqual(segs[0][0], 0.0)
        self.assertAlmostEqual(segs[0][1], 8.0)
        self.assertIn("CUT TAIL", desc)

    def test_cut_range_head(self):
        # Cut [0.0, 3.0] from 10s video -> keep [3.0, 10.0]
        segs, desc = resolve_keep_segments(10.0, cut_str="0:3.0")
        self.assertEqual(len(segs), 1)
        self.assertAlmostEqual(segs[0][0], 3.0)
        self.assertAlmostEqual(segs[0][1], 10.0)

    def test_cut_range_middle(self):
        # Cut [3.0, 6.0] from 10s video -> keep [0.0, 3.0] and [6.0, 10.0]
        segs, desc = resolve_keep_segments(10.0, cut_str="3.0:6.0")
        self.assertEqual(len(segs), 2)
        self.assertAlmostEqual(segs[0][0], 0.0)
        self.assertAlmostEqual(segs[0][1], 3.0)
        self.assertAlmostEqual(segs[1][0], 6.0)
        self.assertAlmostEqual(segs[1][1], 10.0)
        self.assertIn("CUT MIDDLE", desc)

    def test_keep_window(self):
        # Keep [2.0, 7.0] from 10s video -> keep [2.0, 7.0]
        segs, desc = resolve_keep_segments(10.0, keep_str="2.0:7.0")
        self.assertEqual(len(segs), 1)
        self.assertAlmostEqual(segs[0][0], 2.0)
        self.assertAlmostEqual(segs[0][1], 7.0)
        self.assertIn("KEEP WINDOW", desc)

    def test_conflict_error(self):
        # Disallow specifying both cut and keep in same command
        with self.assertRaises(CutError):
            resolve_keep_segments(10.0, cut_str="0:2.0", keep_str="2.0:8.0")


class TestFFmpegCommandBuilding(unittest.TestCase):
    """Test FFmpeg command construction."""

    def test_build_cmd_single_segment(self):
        cmd = build_ffmpeg_cmd(
            input_path=Path("/tmp/in.mp4"),
            output_path=Path("/tmp/out.mp4"),
            segments=[(2.0, 8.0)],
            has_audio=True,
            crf=18,
        )
        self.assertEqual(cmd[0], "ffmpeg")
        self.assertIn("-ss", cmd)
        self.assertIn("-t", cmd)
        self.assertIn("libx264", cmd)
        self.assertIn("aac", cmd)

    def test_build_cmd_multiple_segments_concat(self):
        cmd = build_ffmpeg_cmd(
            input_path=Path("/tmp/in.mp4"),
            output_path=Path("/tmp/out.mp4"),
            segments=[(0.0, 2.0), (5.0, 10.0)],
            has_audio=True,
            crf=18,
        )
        self.assertIn("-filter_complex", cmd)
        fc_idx = cmd.index("-filter_complex")
        filter_str = cmd[fc_idx + 1]
        self.assertIn("concat=n=2:v=1:a=1", filter_str)


class TestVideoCuttingIntegration(unittest.TestCase):
    """Integration test running real FFmpeg edits on generated test clips."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = Path(tempfile.mkdtemp(prefix="cut_test_"))
        cls.sample_video = cls.temp_dir / "sample_5s.mp4"

        # Generate a 5-second synthetic test video with audio using FFmpeg
        cmd = [
            "ffmpeg",
            "-y",
            "-f", "lavfi",
            "-i", "testsrc=duration=5:size=320x240:rate=30",
            "-f", "lavfi",
            "-i", "sine=frequency=1000:duration=5",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            str(cls.sample_video),
        ]
        subprocess.run(cmd, check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_cut_start_head_removal(self):
        out_video = self.temp_dir / "cut_head.mp4"
        # Cut first 2.0s off a 5s video -> output duration should be ~3.0s
        cut_video(
            input_path=self.sample_video,
            output_path=out_video,
            cut_start_sec=2.0,
        )
        self.assertTrue(out_video.is_file())
        info = get_media_info(out_video)
        self.assertAlmostEqual(info.duration, 3.0, delta=0.15)

    def test_cut_middle_and_splice(self):
        out_video = self.temp_dir / "cut_middle.mp4"
        # Cut [1.0, 3.0] (2s) from a 5s video -> output duration should be ~3.0s (1s + 2s)
        cut_video(
            input_path=self.sample_video,
            output_path=out_video,
            cut_str="1.0:3.0",
        )
        self.assertTrue(out_video.is_file())
        info = get_media_info(out_video)
        self.assertAlmostEqual(info.duration, 3.0, delta=0.15)

    def test_keep_window(self):
        out_video = self.temp_dir / "keep_win.mp4"
        # Keep [1.5, 4.0] (2.5s) from 5s video -> output duration should be ~2.5s
        cut_video(
            input_path=self.sample_video,
            output_path=out_video,
            keep_str="1.5:4.0",
        )
        self.assertTrue(out_video.is_file())
        info = get_media_info(out_video)
        self.assertAlmostEqual(info.duration, 2.5, delta=0.15)


if __name__ == "__main__":
    unittest.main()

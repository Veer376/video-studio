#!/usr/bin/env python3
"""
add_loop.py

Transform a video into an endless/seamless loop for YouTube Shorts / Reels / TikTok.
Splits the video at a mandatory timestamp, places the trailing segment ([timestamp -> end])
first, followed by the leading segment ([0 -> timestamp]), and concatenates them into
the final output video.

Usage:
    python3 scripts/add_loop.py -i input.mp4 -t 45.5 -o output_looped.mp4
    python3 scripts/add_loop.py --input input.mp4 --timestamp 00:00:45 --output output_looped.mp4
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


class LoopError(RuntimeError):
    """Raised when video looping fails."""


def parse_timestamp(ts_str: str) -> float:
    """
    Parse a timestamp string into float seconds.
    Supports:
      - Raw seconds: "45", "45.5", "52s"
      - Dot minute.second notation: "0.52" -> 52s, "1.15" -> 75s
      - MM:SS / MM:SS.mmm: "01:15", "00:52", "01:15.500"
      - HH:MM:SS / HH:MM:SS.mmm: "00:01:15", "01:30:00.250"
    """
    ts_str = ts_str.strip().lower()
    if not ts_str:
        raise ValueError("Timestamp cannot be empty.")

    if ts_str.endswith("s"):
        ts_str = ts_str[:-1].strip()

    # Check for HH:MM:SS or MM:SS format
    if ":" in ts_str:
        parts = ts_str.split(":")
        if len(parts) == 2:  # MM:SS
            minutes = float(parts[0])
            seconds = float(parts[1])
            if minutes < 0 or seconds < 0 or seconds >= 60:
                raise ValueError(f"Invalid MM:SS timestamp: '{ts_str}'")
            return minutes * 60.0 + seconds
        elif len(parts) == 3:  # HH:MM:SS
            hours = float(parts[0])
            minutes = float(parts[1])
            seconds = float(parts[2])
            if hours < 0 or minutes < 0 or minutes >= 60 or seconds < 0 or seconds >= 60:
                raise ValueError(f"Invalid HH:MM:SS timestamp: '{ts_str}'")
            return hours * 3600.0 + minutes * 60.0 + seconds
        else:
            raise ValueError(f"Unsupported timestamp format: '{ts_str}'")

    # Check for MM.SS dot notation (e.g. "0.52" = 0m52s = 52s, "1.20" = 1m20s = 80s)
    # where the fractional part is 2 digits representing seconds (10..59)
    dot_match = re.match(r"^(\d+)\.(\d{2})$", ts_str)
    if dot_match:
        mins = int(dot_match.group(1))
        secs = int(dot_match.group(2))
        if secs < 60 and (mins > 0 or secs >= 10):
            # Interpreted as M.SS (e.g. 0.52 -> 52s)
            return mins * 60.0 + float(secs)

    try:
        val = float(ts_str)
        if val < 0:
            raise ValueError(f"Timestamp cannot be negative: {val}")
        return val
    except ValueError as exc:
        raise ValueError(f"Could not parse timestamp '{ts_str}': {exc}") from exc


def format_seconds(seconds: float) -> str:
    """Format seconds into HH:MM:SS.mmm string."""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hrs:02d}:{mins:02d}:{secs:06.3f}"


def probe_video(input_path: Path) -> dict[str, any]:
    """Inspect input media streams and duration using ffprobe."""
    if not shutil.which("ffprobe"):
        raise LoopError("ffprobe is required on PATH but was not found.")

    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration,size,bit_rate",
        "-show_entries",
        "stream=codec_type,codec_name,width,height,r_frame_rate",
        "-of",
        "json",
        str(input_path),
    ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(res.stdout)
    except subprocess.CalledProcessError as exc:
        raise LoopError(f"ffprobe failed on {input_path}: {exc.stderr.strip()}") from exc
    except json.JSONDecodeError as exc:
        raise LoopError(f"Failed to parse ffprobe output: {exc}") from exc

    format_info = data.get("format", {})
    duration_str = format_info.get("duration")
    if not duration_str:
        raise LoopError(f"Could not determine duration for video: {input_path}")

    duration = float(duration_str)
    streams = data.get("streams", [])
    has_video = any(s.get("codec_type") == "video" for s in streams)
    has_audio = any(s.get("codec_type") == "audio" for s in streams)

    if not has_video:
        raise LoopError(f"Input file contains no video streams: {input_path}")

    return {
        "duration": duration,
        "has_audio": has_audio,
        "format": format_info,
        "streams": streams,
    }


def add_loop(
    input_path: Path,
    timestamp: float,
    output_path: Path,
    crf: int = 18,
    preset: str = "fast",
    dry_run: bool = False,
) -> None:
    """
    Split input video at timestamp and rearrange Part 2 ([timestamp -> end]) + Part 1 ([0 -> timestamp]).
    """
    if not input_path.exists():
        raise LoopError(f"Input file does not exist: {input_path}")

    if not shutil.which("ffmpeg"):
        raise LoopError("ffmpeg is required on PATH but was not found.")

    # Probe media info
    info = probe_video(input_path)
    total_duration = info["duration"]
    has_audio = info["has_audio"]

    if timestamp <= 0 or timestamp >= total_duration:
        raise LoopError(
            f"Timestamp {timestamp:.3f}s ({format_seconds(timestamp)}) is invalid. "
            f"Must be strictly between 0 and total duration {total_duration:.3f}s ({format_seconds(total_duration)})."
        )

    part1_duration = timestamp
    part2_duration = total_duration - timestamp

    print("=" * 65)
    print("🎬 ADD LOOP: Video Loop Generator")
    print("=" * 65)
    print(f"  • Input video:       {input_path}")
    print(f"  • Total duration:    {total_duration:.3f}s ({format_seconds(total_duration)})")
    print(f"  • Loop split point:  {timestamp:.3f}s ({format_seconds(timestamp)})")
    print(f"  • Part 1 (0 -> T):   {part1_duration:.3f}s (will become second half)")
    print(f"  • Part 2 (T -> End): {part2_duration:.3f}s (will become opening)")
    print(f"  • Output video:      {output_path}")
    print(f"  • Audio stream:      {'Yes (synced)' if has_audio else 'No audio'}")
    print(f"  • Encoding:          H.264 (CRF {crf}, preset '{preset}')")
    print("=" * 65)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Build FFmpeg filter_complex command
    # Part 2: [timestamp -> total_duration] -> [v1], [a1]
    # Part 1: [0 -> timestamp]              -> [v2], [a2]
    # Concat: [v1][v2] / [a1][a2]
    t_str = f"{timestamp:.6f}"
    dur_str = f"{total_duration:.6f}"

    if has_audio:
        filter_complex = (
            f"[0:v]trim=start={t_str}:end={dur_str},setpts=PTS-STARTPTS[v1]; "
            f"[0:a]atrim=start={t_str}:end={dur_str},asetpts=PTS-STARTPTS[a1]; "
            f"[0:v]trim=start=0:end={t_str},setpts=PTS-STARTPTS[v2]; "
            f"[0:a]atrim=start=0:end={t_str},asetpts=PTS-STARTPTS[a2]; "
            f"[v1][a1][v2][a2]concat=n=2:v=1:a=1[v][a]"
        )
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-filter_complex",
            filter_complex,
            "-map",
            "[v]",
            "-map",
            "[a]",
            "-c:v",
            "libx264",
            "-crf",
            str(crf),
            "-preset",
            preset,
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            str(output_path),
        ]
    else:
        filter_complex = (
            f"[0:v]trim=start={t_str}:end={dur_str},setpts=PTS-STARTPTS[v1]; "
            f"[0:v]trim=start=0:end={t_str},setpts=PTS-STARTPTS[v2]; "
            f"[v1][v2]concat=n=2:v=1:a=0[v]"
        )
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-filter_complex",
            filter_complex,
            "-map",
            "[v]",
            "-c:v",
            "libx264",
            "-crf",
            str(crf),
            "-preset",
            preset,
            str(output_path),
        ]

    if dry_run:
        print("\n[DRY RUN] FFmpeg command:")
        print(" ".join(cmd))
        print("\nDry run completed successfully.")
        return

    print("\n⏳ Processing video loop with FFmpeg...")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as exc:
        raise LoopError(f"FFmpeg failed with exit code {exc.returncode}:\n{exc.stderr}") from exc

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise LoopError(f"Output file was not created or is empty: {output_path}")

    # Verify output duration
    out_info = probe_video(output_path)
    out_dur = out_info["duration"]
    out_size = output_path.stat().st_size / (1024 * 1024)

    print(f"✅ Looped video successfully rendered!")
    print(f"  • Saved to: {output_path} ({out_size:.2f} MB)")
    print(f"  • Output duration: {out_dur:.3f}s ({format_seconds(out_dur)})")
    print(f"  • Loop structure: [{part2_duration:.2f}s tail] -> [{part1_duration:.2f}s head]")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Transform a video into an endless loop by splitting at a timestamp and putting the last part first.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/add_loop.py -i video.mp4 -t 45.5 -o looped.mp4
  python3 scripts/add_loop.py --input video.mp4 --timestamp 00:00:50 --output looped.mp4
  python3 scripts/add_loop.py -i input.mp4 -t 1:15 -o output.mp4 --crf 16 --preset slow
        """,
    )

    # Mandatory arguments
    parser.add_argument(
        "-i",
        "--input",
        required=True,
        type=Path,
        help="[MANDATORY] Path to the source input video file.",
    )
    parser.add_argument(
        "-t",
        "--timestamp",
        required=True,
        type=str,
        help="[MANDATORY] Timestamp to split at (seconds e.g. '45.5', 'MM:SS', or 'HH:MM:SS').",
    )
    parser.add_argument(
        "-o",
        "--output",
        required=True,
        type=Path,
        help="[MANDATORY] Path for the output looped video file.",
    )

    # Optional configuration
    parser.add_argument(
        "--crf",
        type=int,
        default=18,
        help="H.264 video quality CRF (default: 18, visually lossless).",
    )
    parser.add_argument(
        "--preset",
        type=str,
        default="fast",
        choices=["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"],
        help="x264 encoding preset (default: 'fast').",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate parameters and print the FFmpeg command without rendering.",
    )

    args = parser.parse_args()

    try:
        ts = parse_timestamp(args.timestamp)
    except ValueError as exc:
        print(f"❌ Error parsing timestamp: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        add_loop(
            input_path=args.input.resolve(),
            timestamp=ts,
            output_path=args.output.resolve(),
            crf=args.crf,
            preset=args.preset,
            dry_run=args.dry_run,
        )
    except LoopError as exc:
        print(f"❌ Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"❌ Unexpected error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

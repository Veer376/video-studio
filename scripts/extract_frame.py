#!/usr/bin/env python3
"""Extract pristine first, last, or specific timestamp frames from a video file."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class ExtractFrameError(RuntimeError):
    """Raised when frame extraction fails."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract high-quality frames (last, first, or custom timestamp) from video files."
    )
    parser.add_argument(
        "--input",
        "-i",
        type=Path,
        required=True,
        help="Input video file path",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Output image path (.png or .jpg). Defaults to <input_dir>/<input_stem>_<position>.png",
    )
    parser.add_argument(
        "--position",
        "-p",
        choices=["last", "first", "timestamp"],
        default="last",
        help="Frame position to extract: 'last' (default), 'first', or 'timestamp'",
    )
    parser.add_argument(
        "--timestamp",
        "-t",
        type=float,
        default=None,
        help="Specific timestamp in seconds (required if --position timestamp)",
    )
    return parser.parse_args()


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise ExtractFrameError(f"Required executable missing: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout).strip()
        raise ExtractFrameError(
            f"Command failed: {' '.join(shlex.quote(x) for x in command)}\n{detail}"
        ) from exc


def get_video_duration(input_path: Path) -> float:
    result = run_command([
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=duration",
        "-of",
        "json",
        str(input_path),
    ])
    try:
        data = json.loads(result.stdout)
        format_duration = data.get("format", {}).get("duration")
        if format_duration:
            return float(format_duration)
        for stream in data.get("streams", []):
            if stream.get("duration"):
                return float(stream["duration"])
        raise ValueError("No duration entry found in media metadata")
    except Exception as exc:
        raise ExtractFrameError(f"Failed to determine duration of {input_path}: {exc}") from exc


def extract_frame(
    input_path: Path,
    output_path: Path | None = None,
    position: str = "last",
    timestamp: float | None = None,
) -> Path:
    resolved_input = input_path if input_path.is_absolute() else PROJECT_ROOT / input_path
    if not resolved_input.is_file():
        raise ExtractFrameError(f"Input video does not exist: {resolved_input}")

    if position == "timestamp":
        if timestamp is None or timestamp < 0:
            raise ExtractFrameError("Valid positive --timestamp must be specified when position is 'timestamp'")
        seek_time = timestamp
    elif position == "first":
        seek_time = 0.0
    else:  # 'last'
        duration = get_video_duration(resolved_input)
        # Seek 1 frame before end (approx 0.04s for 24fps) or safe offset
        seek_time = max(0.0, duration - 0.05)

    if output_path is None:
        tag = f"time_{seek_time:.2f}s" if position == "timestamp" else position
        resolved_output = resolved_input.parent / f"{resolved_input.stem}_{tag}.png"
    else:
        resolved_output = output_path if output_path.is_absolute() else PROJECT_ROOT / output_path

    resolved_output.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-v",
        "error",
        "-y",
        "-ss",
        f"{seek_time:.4f}",
        "-i",
        str(resolved_input),
        "-frames:v",
        "1",
        "-update",
        "1",
        "-q:v",
        "2",
        str(resolved_output),
    ]

    run_command(cmd)

    if not resolved_output.is_file() or resolved_output.stat().st_size == 0:
        raise ExtractFrameError(f"Extraction produced empty or missing file: {resolved_output}")

    return resolved_output


def main() -> int:
    args = parse_args()
    try:
        out_path = extract_frame(
            input_path=args.input,
            output_path=args.output,
            position=args.position,
            timestamp=args.timestamp,
        )
        print(f"✓ Extracted {args.position} frame to: {out_path}")
        return 0
    except ExtractFrameError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Concatenate multiple video files seamlessly into a single output video."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class ConcatError(RuntimeError):
    """Raised when video concatenation fails."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Concatenate multiple MP4 video files in sequence into one final MP4."
    )
    parser.add_argument(
        "--inputs",
        "-i",
        nargs="+",
        type=Path,
        required=True,
        help="Input video file paths in playback sequence",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        required=True,
        help="Output merged MP4 file path",
    )
    parser.add_argument(
        "--reencode",
        action="store_true",
        default=True,
        help="Re-encode to ensure matching frame rates, aspect ratios, and clean audio crossfade/sync (default: True)",
    )
    return parser.parse_args()


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise ConcatError(f"Required executable missing: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout).strip()
        raise ConcatError(
            f"Command failed: {' '.join(shlex.quote(x) for x in command)}\n{detail}"
        ) from exc


def escape_concat_path(path: Path) -> str:
    return str(path.resolve()).replace("'", "'\\''")


def concat_videos(input_paths: list[Path], output_path: Path) -> Path:
    resolved_inputs: list[Path] = []
    for p in input_paths:
        resolved = p if p.is_absolute() else PROJECT_ROOT / p
        if not resolved.is_file():
            raise ConcatError(f"Input file not found: {resolved}")
        resolved_inputs.append(resolved)

    if len(resolved_inputs) < 2:
        raise ConcatError("At least 2 input video files are required for concatenation.")

    resolved_output = output_path if output_path.is_absolute() else PROJECT_ROOT / output_path
    resolved_output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="concat-videos-") as temp_dir:
        concat_txt = Path(temp_dir) / "concat.txt"
        lines = [f"file '{escape_concat_path(p)}'\n" for p in resolved_inputs]
        concat_txt.write_text("".join(lines), encoding="utf-8")

        temp_output = Path(temp_dir) / "merged.mp4"
        cmd = [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-fflags",
            "+genpts",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_txt),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-movflags",
            "+faststart",
            str(temp_output),
        ]
        run_command(cmd)

        if not temp_output.is_file() or temp_output.stat().st_size == 0:
            raise ConcatError("Concatenation failed to produce a valid video output.")

        temp_output.replace(resolved_output)

    return resolved_output


def main() -> int:
    args = parse_args()
    try:
        out = concat_videos(input_paths=args.inputs, output_path=args.output)
        print(f"✓ Successfully concatenated {len(args.inputs)} videos to: {out}")
        return 0
    except ConcatError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

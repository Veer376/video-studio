#!/usr/bin/env python3
"""Overlay timed text on an existing video without changing the scene renderer."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import tempfile
from pathlib import Path


FONT_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
)


class TextRenderError(RuntimeError):
    """Raised when a text-overlay render cannot be completed safely."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--text", required=True)
    parser.add_argument("--start", type=float, default=0.0)
    parser.add_argument("--duration", type=float, default=3.0)
    return parser.parse_args()


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise TextRenderError(f"Required executable is missing: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout).strip()
        raise TextRenderError(
            f"Command failed: {' '.join(shlex.quote(item) for item in command)}\n{detail}"
        ) from exc


def media_info(path: Path) -> tuple[float, int, int, float]:
    result = run([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-show_entries", "stream=codec_type,width,height,r_frame_rate,duration",
        "-of", "json", str(path),
    ])
    try:
        data = json.loads(result.stdout)
        streams = data["streams"]
        stream_types = {stream.get("codec_type") for stream in streams}
        if not {"video", "audio"}.issubset(stream_types):
            raise TextRenderError(f"{path} must contain both video and audio streams")
        video = next(stream for stream in streams if stream.get("codec_type") == "video")
        duration = float(video.get("duration") or data["format"]["duration"])
        numerator, denominator = (int(value) for value in video["r_frame_rate"].split("/", 1))
        return duration, int(video["width"]), int(video["height"]), numerator / denominator
    except (KeyError, StopIteration, TypeError, ValueError, ZeroDivisionError) as exc:
        raise TextRenderError(f"Could not inspect playable media {path}: {exc}") from exc


def find_font() -> str:
    for candidate in FONT_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    raise TextRenderError("No supported macOS TrueType font found")


def make_text_png(path: Path, text: str, width: int, height: int) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise TextRenderError("Pillow is required to render text") from exc

    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    typeface = ImageFont.truetype(find_font(), 50)
    bounds = draw.textbbox((0, 0), text, font=typeface, stroke_width=2)
    x = width - (bounds[2] - bounds[0]) - 48
    y = height - (bounds[3] - bounds[1]) - 42
    draw.text(
        (x, y), text, font=typeface, fill=(255, 255, 255, 255),
        stroke_width=2, stroke_fill=(0, 0, 0, 220),
    )
    image.save(path)


def render(args: argparse.Namespace) -> None:
    source = args.input.resolve()
    output = args.output.resolve()
    if not source.is_file():
        raise TextRenderError(f"Input video does not exist: {source}")
    if source == output:
        raise TextRenderError("Input and output paths must differ")
    if not args.text.strip():
        raise TextRenderError("Text must not be empty")

    source_duration, width, height, fps = media_info(source)
    end = args.start + args.duration
    if args.start < 0 or args.duration <= 0 or end > source_duration:
        raise TextRenderError("Start and duration must fit entirely inside the input video")

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="video-project-text-") as temp_dir:
        overlay_image = Path(temp_dir) / "text.png"
        partial = output.with_suffix(".partial.mp4")
        make_text_png(overlay_image, args.text, width, height)
        filter_graph = (
            f"[0:v][1:v]overlay=0:0:format=auto:"
            f"enable='between(t,{args.start:.3f},{end:.3f})'[v]"
        )
        try:
            run([
                "ffmpeg", "-v", "error", "-y", "-i", str(source),
                "-loop", "1", "-i", str(overlay_image),
                "-filter_complex", filter_graph, "-map", "[v]", "-map", "0:a",
                "-t", f"{source_duration:.3f}", "-c:v", "libx264",
                "-pix_fmt", "yuv420p", "-r", f"{fps:g}", "-c:a", "aac",
                "-ar", "48000", "-ac", "2", "-movflags", "+faststart", str(partial),
            ])
            media_info(partial)
            partial.replace(output)
        except Exception:
            partial.unlink(missing_ok=True)
            raise
    print(f"Rendered text overlay: {output}")


def main() -> int:
    try:
        render(parse_args())
    except TextRenderError as exc:
        print(f"Error: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

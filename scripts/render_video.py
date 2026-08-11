#!/usr/bin/env python3
"""Concatenate canonical scene videos and add the story's rewind title overlay."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import tempfile
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = PROJECT_ROOT / "stories" / "aloo-flood-rescue" / "scenes.json"
DEFAULT_TITLE = "One Hour Before..."
DEFAULT_TITLE_START = 21.0
DEFAULT_TITLE_DURATION = 3.0
FONT_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
)


class RenderError(RuntimeError):
    """Raised when the final render cannot be assembled safely."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Final MP4 path (default: <story>/output/final-video.mp4)",
    )
    parser.add_argument("--title", default=DEFAULT_TITLE)
    parser.add_argument("--title-start", type=float, default=DEFAULT_TITLE_START)
    parser.add_argument("--title-duration", type=float, default=DEFAULT_TITLE_DURATION)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RenderError(f"Required executable is missing: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout).strip()
        raise RenderError(
            f"Command failed: {' '.join(shlex.quote(x) for x in command)}\n{detail}"
        ) from exc


def resolve_path(path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def load_scenes(config_path: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RenderError(f"Cannot read scene configuration {config_path}: {exc}") from exc
    scenes = data.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise RenderError("scenes.json must contain a non-empty scenes array")
    ids: set[str] = set()
    for scene in scenes:
        if not isinstance(scene, dict) or not isinstance(scene.get("id"), str):
            raise RenderError("Every scene must be an object with a string id")
        if scene["id"] in ids:
            raise RenderError(f"Duplicate scene id: {scene['id']}")
        ids.add(scene["id"])
        output_path = scene.get("output_path")
        if not isinstance(output_path, str) or not output_path:
            raise RenderError(f"Scene {scene['id']} has no output_path")
    return scenes


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
            raise RenderError(f"{path} must contain both video and audio streams")
        video = next(stream for stream in streams if stream.get("codec_type") == "video")
        duration = float(video.get("duration") or data["format"]["duration"])
        width = int(video["width"])
        height = int(video["height"])
        numerator, denominator = (int(x) for x in video["r_frame_rate"].split("/", 1))
        return duration, width, height, numerator / denominator
    except (KeyError, StopIteration, TypeError, ValueError, ZeroDivisionError) as exc:
        raise RenderError(f"Could not inspect playable media {path}: {exc}") from exc


def escape_concat_path(path: Path) -> str:
    return str(path.resolve()).replace("'", "'\\''")


def find_font() -> str:
    for candidate in FONT_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    raise RenderError("No supported macOS TrueType font found for the title card")


def make_title_png(path: Path, title: str, width: int, height: int) -> None:
    font = find_font()
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise RenderError("Pillow is required to render the title card") from exc
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    typeface = ImageFont.truetype(font, 50)
    bounds = draw.textbbox((0, 0), title, font=typeface, stroke_width=2)
    text_width = bounds[2] - bounds[0]
    text_height = bounds[3] - bounds[1]
    x = width - text_width - 48
    y = height - text_height - 42
    draw.text(
        (x, y), title, font=typeface, fill=(255, 255, 255, 255),
        stroke_width=2, stroke_fill=(0, 0, 0, 220),
    )
    image.save(path)


def overlay_title_on_video(
    source: Path,
    destination: Path,
    title_image: Path,
    start: float,
    duration: float,
    source_duration: float,
    fps: float,
) -> None:
    if start < 0 or duration <= 0 or start + duration > source_duration:
        raise RenderError("Title start and duration must fit entirely inside the final video")
    title_end = start + duration
    overlay = f"[0:v][1:v]overlay=0:0:format=auto:enable='between(t,{start:.3f},{title_end:.3f})'[v]"
    run([
        "ffmpeg", "-v", "error", "-y", "-i", str(source),
        "-loop", "1", "-i", str(title_image),
        "-filter_complex", overlay, "-map", "[v]", "-map", "0:a",
        "-t", f"{source_duration:.3f}", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-r", f"{fps:g}", "-c:a", "aac", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart", str(destination),
    ])


def render(args: argparse.Namespace) -> None:
    config_path = args.config if args.config.is_absolute() else PROJECT_ROOT / args.config
    scenes = load_scenes(config_path)

    scene_paths: list[Path] = []
    durations: list[float] = []
    width = height = 0
    fps = 0.0
    for scene in scenes:
        path = resolve_path(scene["output_path"])
        if not path.is_file():
            raise RenderError(f"Missing canonical scene video: {path}")
        duration, scene_width, scene_height, scene_fps = media_info(path)
        if not width:
            width, height, fps = scene_width, scene_height, scene_fps
        elif (scene_width, scene_height, scene_fps) != (width, height, fps):
            raise RenderError(f"Scene {scene['id']} format differs from the first scene")
        scene_paths.append(path)
        durations.append(duration)

    base_duration = sum(durations)
    title_start = args.title_start
    title_end = title_start + args.title_duration
    if title_start < 0 or args.title_duration <= 0 or title_end > base_duration:
        raise RenderError("Title start and duration must fit entirely inside the final video")
    if args.output is None:
        output = config_path.parent / "output" / "final-video.mp4"
    else:
        output = args.output if args.output.is_absolute() else PROJECT_ROOT / args.output
    print(f"Scenes: {len(scenes)}")
    print("Black transition: none")
    print(f"Title overlay pass: final timeline, {title_start:.3f}s–{title_end:.3f}s")
    print(f"Output: {output}")
    if args.dry_run:
        return

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="video-project-render-") as temp_dir:
        temp = Path(temp_dir)
        title_image = temp / "title_overlay.png"
        concat_file = temp / "concat.txt"
        base_video = temp / "base.concat.mp4"
        partial = temp / "final.partial.mp4"
        make_title_png(title_image, args.title, width, height)
        concat_entries = scene_paths
        concat_file.write_text(
            "".join(f"file '{escape_concat_path(path)}'\n" for path in concat_entries),
            encoding="utf-8",
        )
        run([
            "ffmpeg", "-v", "error", "-y", "-fflags", "+genpts",
            "-f", "concat", "-safe", "0", "-i", str(concat_file),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
            "-ar", "48000", "-ac", "2", "-movflags", "+faststart", str(base_video),
        ])
        base_duration, _, _, base_fps = media_info(base_video)
        overlay_title_on_video(
            base_video, partial, title_image, title_start, args.title_duration,
            base_duration, base_fps,
        )
        media_info(partial)
        partial.replace(output)
    print(f"Rendered {output}")


def main() -> int:
    try:
        render(parse_args())
    except RenderError as exc:
        print(f"Error: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

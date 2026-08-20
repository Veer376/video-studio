#!/usr/bin/env python3
"""Concatenate canonical scene videos into one final MP4."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import tempfile
from pathlib import Path
from typing import Any

try:
    from .review_contract import (
        ReviewContractError,
        validate_canonical_binding,
        validate_review,
    )
except ImportError:  # Direct execution: python3 scripts/render_video.py
    from review_contract import (
        ReviewContractError,
        validate_canonical_binding,
        validate_review,
    )


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = PROJECT_ROOT / "stories" / "aloo-flood-rescue" / "scenes.json"


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
    parser.add_argument(
        "--watermark-image",
        type=Path,
        default=None,
        help="Optional channel logo / badge image path to mask AI watermark on the final render",
    )
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


def validate_scene_review(
    config_path: Path,
    scene_id: str,
    canonical: Path | None = None,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    try:
        review, _ = validate_review(config_path, scene_id, project_root)
        if canonical is not None:
            validate_canonical_binding(review, canonical, project_root)
    except ReviewContractError as exc:
        raise RenderError(str(exc)) from exc
    return review


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


def render(args: argparse.Namespace) -> None:
    config_path = args.config if args.config.is_absolute() else PROJECT_ROOT / args.config
    scenes = load_scenes(config_path)

    scene_paths: list[Path] = []
    width = height = 0
    fps = 0.0
    for scene in scenes:
        path = resolve_path(scene["output_path"])
        if not path.is_file():
            raise RenderError(f"Missing canonical scene video: {path}")
        validate_scene_review(config_path, scene["id"], path)
        _, scene_width, scene_height, scene_fps = media_info(path)
        if not width:
            width, height, fps = scene_width, scene_height, scene_fps
        elif (scene_width, scene_height, scene_fps) != (width, height, fps):
            raise RenderError(f"Scene {scene['id']} format differs from the first scene")
        scene_paths.append(path)
    if args.output is None:
        output = config_path.parent / "output" / "final-video.mp4"
    else:
        output = args.output if args.output.is_absolute() else PROJECT_ROOT / args.output
    print(f"Scenes: {len(scenes)}")
    print("Black transition: none")
    print(f"Output: {output}")
    if args.dry_run:
        return

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="video-project-render-") as temp_dir:
        temp = Path(temp_dir)
        concat_file = temp / "concat.txt"
        partial = temp / "final.partial.mp4"
        concat_file.write_text(
            "".join(f"file '{escape_concat_path(path)}'\n" for path in scene_paths),
            encoding="utf-8",
        )
        run([
            "ffmpeg", "-v", "error", "-y", "-fflags", "+genpts",
            "-f", "concat", "-safe", "0", "-i", str(concat_file),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
            "-ar", "48000", "-ac", "2", "-movflags", "+faststart", str(partial),
        ])
        media_info(partial)
        if args.watermark_image:
            wm_img_path = (
                args.watermark_image
                if args.watermark_image.is_absolute()
                else PROJECT_ROOT / args.watermark_image
            )
            from apply_watermark import apply_watermark
            wm_partial = temp / "final.watermarked.mp4"
            apply_watermark(
                input_video=partial,
                output_video=wm_partial,
                image_path=wm_img_path,
            )
            wm_partial.replace(output)
        else:
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

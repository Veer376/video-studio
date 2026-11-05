from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from PIL import Image


def verify_image(path: Path) -> None:
    if not path.is_file() or path.stat().st_size <= 0:
        raise ValueError(f"Image output is missing or empty: {path}")
    try:
        with Image.open(path) as image:
            image.verify()
    except Exception as exc:
        raise ValueError(f"Invalid image output {path}: {exc}") from exc


def verify_video(path: Path) -> None:
    if not path.is_file() or path.stat().st_size <= 0:
        raise ValueError(f"Video output is missing or empty: {path}")
    if shutil.which("ffprobe") is None:
        raise RuntimeError("ffprobe is required to verify generated videos")
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type:format=duration",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ValueError(f"ffprobe rejected {path}: {result.stderr.strip()}")
    data = json.loads(result.stdout or "{}")
    streams = {stream.get("codec_type") for stream in data.get("streams", [])}
    if "video" not in streams:
        raise ValueError(f"Generated file has no video stream: {path}")
    try:
        duration = float((data.get("format") or {}).get("duration") or 0)
    except (TypeError, ValueError):
        duration = 0
    if duration <= 0:
        raise ValueError(f"Generated video has no positive duration: {path}")


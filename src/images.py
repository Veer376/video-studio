from __future__ import annotations

from pathlib import Path

import ffmpeg


def validate_image(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")
    ffmpeg.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "json", str(path)])

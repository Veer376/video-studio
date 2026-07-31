from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


class FFmpegError(RuntimeError):
    pass


def require_tools() -> None:
    missing = [tool for tool in ("ffmpeg", "ffprobe") if shutil.which(tool) is None]
    if missing:
        raise FFmpegError(f"Missing required tool(s): {', '.join(missing)}")


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        tail = (result.stderr or result.stdout)[-3000:]
        raise FFmpegError(f"Command failed: {' '.join(args)}\n{tail}")
    return result


def probe_duration(path: Path) -> float:
    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ]
    )
    data = json.loads(result.stdout)
    return float(data["format"]["duration"])


def video_has_stream(path: Path) -> bool:
    result = run(["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(path)])
    data = json.loads(result.stdout)
    return bool(data.get("streams"))


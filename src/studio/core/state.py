from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from studio.core.io import read_json


STAGES = ("voice", "illustrate", "render")


@dataclass(frozen=True)
class StageState:
    name: str
    complete: bool
    missing: tuple[str, ...]


def load_scenes(project_dir: Path) -> dict[str, Any] | None:
    path = project_dir / "scenes.json"
    if not path.exists():
        return None
    return read_json(path)


def scene_items(project_dir: Path) -> list[dict[str, Any]]:
    scenes_data = load_scenes(project_dir)
    if not scenes_data:
        return []
    return list(scenes_data.get("scenes") or [])


def voice_state(project_dir: Path) -> StageState:
    missing: list[str] = []
    if not (project_dir / "audio" / "narration.wav").exists():
        missing.append("audio/narration.wav")
    if not (project_dir / "audio" / "timestamps.json").exists():
        missing.append("audio/timestamps.json")
    scenes = scene_items(project_dir)
    if not scenes:
        missing.append("scenes.json")
    for scene in scenes:
        if not isinstance(scene.get("start_time"), (int, float)):
            missing.append(f"{scene.get('id', '<unknown>')}.start_time")
        if not isinstance(scene.get("end_time"), (int, float)):
            missing.append(f"{scene.get('id', '<unknown>')}.end_time")
    return StageState("voice", not missing, tuple(missing))


def illustrate_state(project_dir: Path) -> StageState:
    missing: list[str] = []
    scenes = scene_items(project_dir)
    if not scenes:
        missing.append("scenes.json")
    for scene in scenes:
        scene_id = scene.get("id", "<unknown>")
        image_path = scene.get("image_path")
        if not image_path:
            missing.append(f"{scene_id}.image_path")
            continue
        if not (project_dir / image_path).exists():
            missing.append(str(image_path))
    return StageState("illustrate", not missing, tuple(missing))


def _ffprobe_streams(path: Path) -> set[str]:
    if shutil.which("ffprobe") is None:
        return set()
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return set()
    data = json.loads(result.stdout or "{}")
    return {stream.get("codec_type") for stream in data.get("streams", [])}


def render_state(project_dir: Path) -> StageState:
    output = project_dir / "output" / "final-video.mp4"
    if not output.exists():
        return StageState("render", False, ("output/final-video.mp4",))
    streams = _ffprobe_streams(output)
    if "video" not in streams or "audio" not in streams:
        return StageState("render", False, ("probeable video+audio streams",))
    return StageState("render", True, ())


def stage_state(project_dir: Path, stage: str) -> StageState:
    if stage == "voice":
        return voice_state(project_dir)
    if stage == "illustrate":
        return illustrate_state(project_dir)
    if stage == "render":
        return render_state(project_dir)
    raise ValueError(f"Unknown stage: {stage}")


def all_states(project_dir: Path) -> list[StageState]:
    return [stage_state(project_dir, stage) for stage in STAGES]


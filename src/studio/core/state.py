from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from studio.core.io import read_json
from studio.core.paths import is_root_asset_locator, resolve_asset_locator


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


def _valid_project_image(project_dir: Path, image_path: str) -> bool:
    project_root = project_dir.resolve()
    resolved = (project_dir / image_path).resolve()
    if not resolved.is_relative_to(project_root) or not resolved.is_file():
        return False
    try:
        with Image.open(resolved) as image:
            image.verify()
        return True
    except (OSError, ValueError):
        return False


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
    scenes_data = load_scenes(project_dir) or {}
    scenes = list(scenes_data.get("scenes") or [])
    if not scenes:
        missing.append("scenes.json")
    characters = scenes_data.get("characters") or {}
    if not isinstance(characters, dict):
        missing.append("scenes.json.characters")
        characters = {}
    for key, character in characters.items():
        image_path = character.get("image_path") if isinstance(character, dict) else None
        if not image_path:
            missing.append(f"characters.{key}.image_path")
            continue
        locator = str(image_path)
        prompt = character.get("prompt") if isinstance(character, dict) else None
        if is_root_asset_locator(locator) and isinstance(prompt, str) and prompt.strip():
            missing.append(f"characters.{key}.root_adaptation")
            continue
        try:
            resolved = resolve_asset_locator(project_dir, locator)
        except ValueError:
            missing.append(str(image_path))
            continue
        local_character_root = (project_dir / "assets" / "characters").resolve()
        if not is_root_asset_locator(locator) and not resolved.is_relative_to(
            local_character_root
        ):
            missing.append(locator)
            continue
        if not resolved.is_file():
            missing.append(locator)
            continue
        try:
            with Image.open(resolved) as image:
                image.verify()
        except (OSError, ValueError):
            missing.append(locator)
    for scene in scenes:
        scene_id = scene.get("id", "<unknown>")
        image_path = scene.get("image_path")
        if not image_path:
            missing.append(f"{scene_id}.image_path")
            continue
        if not _valid_project_image(project_dir, str(image_path)):
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

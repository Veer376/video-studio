from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import Manifest, ManifestError, Motion, Project, Scene, Transition, Voice


def load_manifest(path: str | Path) -> Manifest:
    manifest_path = Path(path)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest = parse_manifest(data)
    manifest.path = manifest_path
    return manifest


def save_manifest(manifest: Manifest, path: str | Path | None = None) -> None:
    out_path = Path(path) if path else manifest.path
    if out_path is None:
        raise ManifestError("Cannot save manifest without a path")
    out_path.write_text(json.dumps(to_dict(manifest), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_manifest(data: dict[str, Any]) -> Manifest:
    required = ["project", "voice", "scenes"]
    for key in required:
        if key not in data:
            raise ManifestError(f"Missing required manifest key: {key}")

    project_data = data["project"]
    project = Project(
        title=_require_str(project_data, "title"),
        language=_require_str(project_data, "language"),
        aspect_ratio=_require_str(project_data, "aspect_ratio"),
        resolution=_require_str(project_data, "resolution"),
        fps=int(project_data.get("fps", 30)),
    )
    width, height = project.width_height
    if width <= 0 or height <= 0:
        raise ManifestError("Resolution dimensions must be positive")
    if project.fps <= 0:
        raise ManifestError("FPS must be positive")

    voice_data = data["voice"]
    voice = Voice(
        provider=_require_str(voice_data, "provider"),
        voice=voice_data.get("voice"),
        instructions=voice_data.get("instructions"),
        model=voice_data.get("model"),
        response_format=str(voice_data.get("response_format", "wav")),
        sample_rate=int(voice_data["sample_rate"]) if voice_data.get("sample_rate") is not None else None,
        speed=float(voice_data["speed"]) if voice_data.get("speed") is not None else None,
        transport=voice_data.get("transport"),
    )
    if voice.response_format not in {"wav", "mp3", "flac", "ogg", "mulaw"}:
        raise ManifestError(f"Unsupported voice response_format: {voice.response_format}")
    if voice.sample_rate is not None and voice.sample_rate not in {8000, 16000, 22050, 24000, 32000, 44100, 48000}:
        raise ManifestError(f"Unsupported voice sample_rate: {voice.sample_rate}")
    if voice.speed is not None and not 0.5 <= voice.speed <= 5:
        raise ManifestError("Voice speed must be between 0.5 and 5")
    if voice.transport is not None and voice.transport not in {"rest", "rest_stream"}:
        raise ManifestError(f"Unsupported voice transport: {voice.transport}")

    scenes: list[Scene] = []
    seen_ids: set[str] = set()
    for raw_scene in data["scenes"]:
        scene_id = _require_str(raw_scene, "id")
        if scene_id in seen_ids:
            raise ManifestError(f"Duplicate scene id: {scene_id}")
        seen_ids.add(scene_id)
        transition_data = raw_scene.get("transition") or {}
        motion_data = raw_scene.get("motion") or {}
        scene = Scene(
            id=scene_id,
            narration=_require_str(raw_scene, "narration"),
            voice_direction=str(raw_scene.get("voice_direction", "")),
            image_prompt=_require_str(raw_scene, "image_prompt"),
            reference_images=list(raw_scene.get("reference_images") or []),
            image_path=raw_scene.get("image_path"),
            audio_path=raw_scene.get("audio_path"),
            duration_seconds=raw_scene.get("duration_seconds"),
            subtitle=str(raw_scene.get("subtitle") or raw_scene["narration"]),
            motion=Motion(
                type=str(motion_data.get("type", "slow_zoom_in")),
                intensity=float(motion_data.get("intensity", 0.04)),
            ),
            transition=Transition(
                type=str(transition_data.get("type", "crossfade")),
                duration_seconds=float(transition_data.get("duration_seconds", 0.6)),
            ),
            errors=list(raw_scene.get("errors") or []),
        )
        if not scene.narration.strip():
            raise ManifestError(f"{scene.id}: narration is empty")
        if scene.duration_seconds is not None and float(scene.duration_seconds) <= 0:
            raise ManifestError(f"{scene.id}: duration_seconds must be positive")
        scenes.append(scene)

    if not scenes:
        raise ManifestError("Manifest must contain at least one scene")

    return Manifest(
        project=project,
        characters=list(data.get("characters") or []),
        visual_style=dict(data.get("visual_style") or {}),
        voice=voice,
        scenes=scenes,
        background_music_path=data.get("background_music_path"),
        subtitles_enabled=bool(data.get("subtitles_enabled", False)),
        target_scene_count=data.get("target_scene_count"),
        target_duration_seconds=data.get("target_duration_seconds"),
    )


def to_dict(manifest: Manifest) -> dict[str, Any]:
    return {
        "project": manifest.project.__dict__,
        "characters": manifest.characters,
        "visual_style": manifest.visual_style,
        "voice": {
            "provider": manifest.voice.provider,
            "voice": manifest.voice.voice,
            "instructions": manifest.voice.instructions,
            "model": manifest.voice.model,
            "response_format": manifest.voice.response_format,
            "sample_rate": manifest.voice.sample_rate,
            "speed": manifest.voice.speed,
            "transport": manifest.voice.transport,
        },
        "background_music_path": manifest.background_music_path,
        "subtitles_enabled": manifest.subtitles_enabled,
        "target_scene_count": manifest.target_scene_count,
        "target_duration_seconds": manifest.target_duration_seconds,
        "scenes": [
            {
                "id": scene.id,
                "narration": scene.narration,
                "voice_direction": scene.voice_direction,
                "image_prompt": scene.image_prompt,
                "reference_images": scene.reference_images,
                "image_path": scene.image_path,
                "audio_path": scene.audio_path,
                "duration_seconds": scene.duration_seconds,
                "subtitle": scene.subtitle,
                "motion": scene.motion.__dict__,
                "transition": scene.transition.__dict__,
                "errors": scene.errors,
            }
            for scene in manifest.scenes
        ],
    }


def validate_assets(manifest: Manifest, base_dir: Path) -> list[str]:
    errors: list[str] = []
    for scene in manifest.scenes:
        if not scene.image_path:
            errors.append(f"{scene.id}: missing image_path")
        elif not (base_dir / scene.image_path).exists():
            errors.append(f"{scene.id}: image not found: {scene.image_path}")
        if not scene.audio_path:
            errors.append(f"{scene.id}: missing audio_path")
        elif not (base_dir / scene.audio_path).exists():
            errors.append(f"{scene.id}: audio not found: {scene.audio_path}")
    return errors


def _require_str(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"Missing or empty string field: {key}")
    return value

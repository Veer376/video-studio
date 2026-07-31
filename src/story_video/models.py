from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class ManifestError(ValueError):
    pass


@dataclass
class Project:
    title: str
    language: str
    aspect_ratio: str
    resolution: str
    fps: int

    @property
    def width_height(self) -> tuple[int, int]:
        try:
            width, height = self.resolution.lower().split("x")
            return int(width), int(height)
        except Exception as exc:
            raise ManifestError(f"Invalid resolution: {self.resolution}") from exc


@dataclass
class Transition:
    type: str = "crossfade"
    duration_seconds: float = 0.6


@dataclass
class Motion:
    type: str = "slow_zoom_in"
    intensity: float = 0.04


@dataclass
class Scene:
    id: str
    narration: str
    voice_direction: str
    image_prompt: str
    reference_images: list[str]
    image_path: str | None
    audio_path: str | None
    duration_seconds: float | None
    subtitle: str
    motion: Motion
    transition: Transition
    errors: list[str] = field(default_factory=list)


@dataclass
class Voice:
    provider: str
    voice: str | None = None
    instructions: str | None = None
    model: str | None = None
    response_format: str = "wav"
    sample_rate: int | None = None
    speed: float | None = None


@dataclass
class Manifest:
    project: Project
    characters: list[dict[str, Any]]
    visual_style: dict[str, Any]
    voice: Voice
    scenes: list[Scene]
    background_music_path: str | None = None
    subtitles_enabled: bool = False
    target_scene_count: int | None = None
    target_duration_seconds: int | None = None
    path: Path | None = None

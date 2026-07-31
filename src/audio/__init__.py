"""Audio package — narration synthesis and pacing.

Public API (same surface as the old audio.py):
    prepare_narration_audio   — generate TTS audio for all scenes
    pace_narration_audio      — apply atempo pacing to raw TTS audio
    measure_scene_audio       — populate scene.duration_seconds from existing audio
    generate_voice_preview    — render a short voice preview clip
    validate_existing_audio   — verify pre-supplied audio files are present and probeable
    set_voice_gender          — set manifest voice to configured gender default
    estimate_placeholder_duration — estimate narration duration from text length
"""
from .base import (
    estimate_placeholder_duration,
    generate_voice_preview,
    measure_scene_audio,
    pace_narration_audio,
    set_voice_gender,
    validate_existing_audio,
)
from .gemini import generate_gemini_audio, generate_gemini_preview
from .groq import generate_groq_audio, generate_groq_preview
from .sarvam import generate_sarvam_audio, generate_sarvam_preview

from models import Manifest
from pathlib import Path


def prepare_narration_audio(manifest: Manifest, base_dir: Path, force: bool = False) -> None:
    """Dispatch to the correct TTS provider based on manifest.voice.provider."""
    provider = manifest.voice.provider
    if provider == "existing_audio":
        validate_existing_audio(manifest, base_dir)
        return
    if provider == "groq_tts":
        generate_groq_audio(manifest, base_dir, force=force)
        return
    if provider == "sarvam_tts":
        generate_sarvam_audio(manifest, base_dir, force=force)
        return
    if provider == "gemini_tts":
        generate_gemini_audio(manifest, base_dir, force=force)
        return
    raise ValueError(f"Unsupported voice provider: {provider}")


__all__ = [
    "prepare_narration_audio",
    "pace_narration_audio",
    "measure_scene_audio",
    "generate_voice_preview",
    "generate_sarvam_preview",
    "generate_groq_preview",
    "generate_gemini_preview",
    "validate_existing_audio",
    "set_voice_gender",
    "estimate_placeholder_duration",
]

"""Generate durable, scene-aware narration units."""
from __future__ import annotations

import hashlib
import re
import wave
from pathlib import Path

from studio.core.io import read_json, write_json
from studio.voice.voice import (
    DEFAULT_GEMINI_TTS_MODEL,
    DEFAULT_GEMINI_TTS_VOICE,
    call_gemini_tts,
    concatenate_wav_files,
    load_api_keys,
    load_env,
)


MAX_UNIT_WORDS = 80
MANIFEST_VERSION = 1


def clean_spoken_text(text: str) -> str:
    """Remove Markdown syntax that must not be spoken and normalize whitespace."""
    return re.sub(r"\s+", " ", text.replace(">", " ")).strip()


def group_scenes(scenes: list[dict], max_words: int = MAX_UNIT_WORDS) -> list[list[dict]]:
    """Group adjacent whole scenes, never splitting or overlapping a scene."""
    groups: list[list[dict]] = []
    current: list[dict] = []
    current_words = 0
    for scene in scenes:
        word_count = max(1, len(clean_spoken_text(scene.get("text", "")).split()))
        if current and current_words + word_count > max_words:
            groups.append(current)
            current = []
            current_words = 0
        current.append(scene)
        current_words += word_count
    if current:
        groups.append(current)
    return groups


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as audio:
        return audio.getnframes() / audio.getframerate()


def _input_hash(text: str, model: str, voice: str) -> str:
    return hashlib.sha256(f"{model}\n{voice}\n{text}".encode("utf-8")).hexdigest()


def _generate_audio(keys: list[str], model: str, voice: str, text: str, output: Path) -> None:
    errors: list[str] = []
    for key_number, key in enumerate(keys, start=1):
        masked = key[:6] + "..." + key[-4:] if len(key) > 10 else "***"
        try:
            print(f"  → Requesting TTS with Key {key_number}/{len(keys)} [{masked}]...", flush=True)
            call_gemini_tts(key, model, voice, text, output)
            return
        except Exception as exc:
            errors.append(f"key {key_number} [{masked}]: {exc}")
            print(f"  ⚠ Key {key_number}/{len(keys)} [{masked}] failed ({str(exc)[:60]}). Rotating immediately to next key...", flush=True)
    raise RuntimeError("All Gemini TTS keys failed: " + " | ".join(errors))


def generate_narration_units(
    project_dir: str | Path,
    *,
    force: bool = False,
    max_unit_words: int = MAX_UNIT_WORDS,
) -> dict:
    """Generate/reuse unit WAVs, write their manifest, and concatenate narration.wav."""
    project_dir = Path(project_dir).resolve()
    scenes_path = project_dir / "scenes.json"
    if not scenes_path.exists():
        raise FileNotFoundError("narration requires scenes.json")
    scenes = list(read_json(scenes_path).get("scenes") or [])
    if not scenes:
        raise RuntimeError("scenes.json contains no scenes")

    load_env()
    keys: list[str] | None = None

    model = DEFAULT_GEMINI_TTS_MODEL
    voice = DEFAULT_GEMINI_TTS_VOICE
    narration_dir = project_dir / "audio" / "narration"
    narration_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = narration_dir / "manifest.json"
    old_units = {}
    if manifest_path.exists():
        old_units = {unit["id"]: unit for unit in read_json(manifest_path).get("units", [])}

    units: list[dict] = []
    unit_wavs: list[Path] = []
    groups = group_scenes(scenes, max_words=max_unit_words)
    print(f"→ Narration: {len(groups)} non-overlapping semantic unit(s)")
    for index, group in enumerate(groups, start=1):
        unit_id = f"unit-{index:03d}"
        audio_path = narration_dir / f"{unit_id}.wav"
        text = clean_spoken_text(" ".join(scene.get("text", "") for scene in group))
        input_hash = _input_hash(text, model, voice)
        previous = old_units.get(unit_id, {})
        reusable = (
            not force
            and audio_path.exists()
            and audio_path.stat().st_size > 44
            and (not previous or previous.get("input_hash") == input_hash)
        )
        if reusable:
            print(f"  {unit_id}: reusing audio")
        else:
            if keys is None:
                keys = load_api_keys()
                if not keys:
                    raise RuntimeError("No Gemini API keys found")
            print(f"  {unit_id}: generating {len(text.split())} words")
            _generate_audio(keys, model, voice, text, audio_path)
        duration = wav_duration(audio_path)
        unit = {
            "id": unit_id,
            "scene_ids": [scene.get("id") for scene in group],
            "text": text,
            "input_hash": input_hash,
            "audio_path": f"audio/narration/{unit_id}.wav",
            "duration": round(duration, 3),
        }
        units.append(unit)
        unit_wavs.append(audio_path)

    manifest = {
        "version": MANIFEST_VERSION,
        "model": model,
        "voice": voice,
        "max_unit_words": max_unit_words,
        "units": units,
    }
    write_json(manifest_path, manifest)

    audio_dir = project_dir / "audio"
    temporary = audio_dir / ".narration.tmp.wav"
    concatenate_wav_files(unit_wavs, temporary)
    temporary.replace(audio_dir / "narration.wav")
    print("✓ Narration audio and manifest complete")
    return manifest

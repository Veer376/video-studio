"""Groq TTS provider."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

import ffmpeg
from models import Manifest
from .base import _raw_audio_path, _ssl_context


def generate_groq_audio(manifest: Manifest, base_dir: Path, force: bool = False) -> None:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set")

    model = manifest.voice.model or "canopylabs/orpheus-v1-english"
    voice = manifest.voice.voice or "autumn"
    response_format = manifest.voice.response_format or "wav"

    for scene in manifest.scenes:
        if len(scene.narration) > 200 and model.startswith("canopylabs/orpheus"):
            raise ValueError(f"{scene.id}: Groq Orpheus TTS input exceeds 200 characters")
        scene.audio_path = _raw_audio_path(scene.id, response_format)
        out_path = base_dir / scene.audio_path
        if out_path.exists() and not force:
            continue
        out_path.parent.mkdir(parents=True, exist_ok=True)
        _call_groq_tts(
            api_key=api_key,
            model=model,
            voice=voice,
            text=scene.narration,
            response_format=response_format,
            sample_rate=manifest.voice.sample_rate,
            speed=manifest.voice.speed,
            out_path=out_path,
        )
        ffmpeg.probe_duration(out_path)


def generate_groq_preview(
    manifest: Manifest,
    base_dir: Path,
    text: str | None = None,
    out_path: Path | None = None,
    force: bool = False,
) -> Path:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set")

    model = manifest.voice.model or "canopylabs/orpheus-v1-english"
    voice = manifest.voice.voice or "autumn"
    response_format = manifest.voice.response_format or "wav"
    preview_text = text or manifest.scenes[0].narration
    if len(preview_text) > 200 and model.startswith("canopylabs/orpheus"):
        raise ValueError("Groq Orpheus TTS preview input exceeds 200 characters")
    extension = "wav" if response_format == "mulaw" else response_format
    destination = out_path or base_dir / f"audio/previews/{model.split('/')[-1]}-{voice}.{extension}"
    if destination.exists() and not force:
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    _call_groq_tts(
        api_key=api_key,
        model=model,
        voice=voice,
        text=preview_text,
        response_format=response_format,
        sample_rate=manifest.voice.sample_rate,
        speed=manifest.voice.speed,
        out_path=destination,
    )
    ffmpeg.probe_duration(destination)
    return destination


def _call_groq_tts(
    *,
    api_key: str,
    model: str,
    voice: str,
    text: str,
    response_format: str,
    sample_rate: int | None,
    speed: float | None,
    out_path: Path,
) -> None:
    body = {
        "model": model,
        "voice": voice,
        "input": text,
        "response_format": response_format,
    }
    if sample_rate is not None:
        body["sample_rate"] = sample_rate
    if speed is not None:
        body["speed"] = speed
    request = urllib.request.Request(
        "https://api.groq.com/openai/v1/audio/speech",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "audio/wav,application/octet-stream,*/*",
            "User-Agent": "story-video-maker/0.1",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90, context=_ssl_context()) as response:
            out_path.write_bytes(response.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1200]
        raise RuntimeError(f"Groq TTS request failed with HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Groq TTS request failed: {exc.reason}") from exc

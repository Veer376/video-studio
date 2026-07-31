"""Sarvam TTS provider (REST and streaming transport)."""
from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

import ffmpeg
from models import Manifest
from .base import _raw_audio_path, _ssl_context


def generate_sarvam_audio(manifest: Manifest, base_dir: Path, force: bool = False) -> None:
    api_key = os.environ.get("SARVAM_API_KEY")
    if not api_key:
        raise RuntimeError("SARVAM_API_KEY is not set")

    model = manifest.voice.model or "bulbul:v3"
    speaker = _sarvam_speaker(manifest)
    response_format = manifest.voice.response_format or "wav"
    transport = manifest.voice.transport or "rest_stream"

    for scene in manifest.scenes:
        text_limit = _sarvam_text_limit(model, transport)
        if len(scene.narration) > text_limit:
            raise ValueError(f"{scene.id}: Sarvam TTS input exceeds {text_limit} characters")
        scene.audio_path = _raw_audio_path(scene.id, response_format)
        out_path = base_dir / scene.audio_path
        if out_path.exists() and not force:
            continue
        out_path.parent.mkdir(parents=True, exist_ok=True)
        _call_sarvam_tts(
            api_key=api_key,
            model=model,
            speaker=speaker,
            text=scene.narration,
            target_language_code=manifest.project.language,
            output_audio_codec=response_format,
            sample_rate=manifest.voice.sample_rate,
            pace=manifest.voice.speed,
            transport=transport,
            out_path=out_path,
        )
        ffmpeg.probe_duration(out_path)


def generate_sarvam_preview(
    manifest: Manifest,
    base_dir: Path,
    text: str | None = None,
    out_path: Path | None = None,
    force: bool = False,
) -> Path:
    api_key = os.environ.get("SARVAM_API_KEY")
    if not api_key:
        raise RuntimeError("SARVAM_API_KEY is not set")

    model = manifest.voice.model or "bulbul:v3"
    speaker = _sarvam_speaker(manifest)
    response_format = manifest.voice.response_format or "wav"
    transport = manifest.voice.transport or "rest_stream"
    preview_text = text or "नमस्ते, आज मैं आपकी क्या मदद कर सकता हूँ?"
    text_limit = _sarvam_text_limit(model, transport)
    if len(preview_text) > text_limit:
        raise ValueError(f"Sarvam TTS preview input exceeds {text_limit} characters")
    destination = out_path or base_dir / f"audio/previews/{model.replace(':', '-')}-{speaker}.{response_format}"
    if destination.exists() and not force:
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    _call_sarvam_tts(
        api_key=api_key,
        model=model,
        speaker=speaker,
        text=preview_text,
        target_language_code=manifest.project.language,
        output_audio_codec=response_format,
        sample_rate=manifest.voice.sample_rate,
        pace=manifest.voice.speed,
        transport=transport,
        out_path=destination,
    )
    ffmpeg.probe_duration(destination)
    return destination


def _sarvam_speaker(manifest: Manifest) -> str:
    return manifest.voice.voice or manifest.voice.female_voice or "priya"


def _sarvam_text_limit(model: str, transport: str | None = None) -> int:
    if (transport or "rest_stream") == "rest_stream":
        return 3500
    return 1500 if model == "bulbul:v2" else 2500


def _call_sarvam_tts(
    *,
    api_key: str,
    model: str,
    speaker: str,
    text: str,
    target_language_code: str,
    output_audio_codec: str,
    sample_rate: int | None,
    pace: float | None,
    transport: str | None,
    out_path: Path,
) -> None:
    if (transport or "rest_stream") == "rest":
        _call_sarvam_tts_rest(
            api_key=api_key,
            model=model,
            speaker=speaker,
            text=text,
            target_language_code=target_language_code,
            output_audio_codec=output_audio_codec,
            sample_rate=sample_rate,
            pace=pace,
            out_path=out_path,
        )
        return
    _call_sarvam_tts_stream(
        api_key=api_key,
        model=model,
        speaker=speaker,
        text=text,
        target_language_code=target_language_code,
        output_audio_codec=output_audio_codec,
        sample_rate=sample_rate,
        pace=pace,
        out_path=out_path,
    )


def _call_sarvam_tts_rest(
    *,
    api_key: str,
    model: str,
    speaker: str,
    text: str,
    target_language_code: str,
    output_audio_codec: str,
    sample_rate: int | None,
    pace: float | None,
    out_path: Path,
) -> None:
    body = {
        "model": model,
        "text": text,
        "target_language_code": target_language_code,
        "speaker": speaker,
        "output_audio_codec": output_audio_codec,
    }
    if sample_rate is not None:
        body["speech_sample_rate"] = sample_rate
    if pace is not None:
        body["pace"] = pace
    request = urllib.request.Request(
        "https://api.sarvam.ai/text-to-speech",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "api-subscription-key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "story-video-maker/0.1",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90, context=_ssl_context()) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1200]
        raise RuntimeError(f"Sarvam TTS request failed with HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Sarvam TTS request failed: {exc.reason}") from exc
    audios = data.get("audios") or []
    if not audios:
        raise RuntimeError("Sarvam TTS response did not contain audio")
    out_path.write_bytes(base64.b64decode(audios[0]))


def _call_sarvam_tts_stream(
    *,
    api_key: str,
    model: str,
    speaker: str,
    text: str,
    target_language_code: str,
    output_audio_codec: str,
    sample_rate: int | None,
    pace: float | None,
    out_path: Path,
) -> None:
    body = {
        "model": model,
        "text": text,
        "target_language_code": target_language_code,
        "speaker": speaker,
        "output_audio_codec": output_audio_codec,
    }
    if sample_rate is not None:
        body["speech_sample_rate"] = sample_rate
    if pace is not None:
        body["pace"] = pace
    request = urllib.request.Request(
        "https://api.sarvam.ai/text-to-speech/stream",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "api-subscription-key": api_key,
            "Content-Type": "application/json",
            "Accept": f"audio/{output_audio_codec},application/octet-stream,*/*",
            "User-Agent": "story-video-maker/0.1",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90, context=_ssl_context()) as response:
            out_path.write_bytes(response.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1200]
        raise RuntimeError(f"Sarvam TTS stream request failed with HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Sarvam TTS stream request failed: {exc.reason}") from exc

"""Gemini TTS provider."""
from __future__ import annotations

import base64
import json
import os
import ssl
import urllib.error
import urllib.request
import wave
from pathlib import Path

import ffmpeg
from models import Manifest
from .base import _raw_audio_path, _ssl_context


def generate_gemini_audio(manifest: Manifest, base_dir: Path, force: bool = False) -> None:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Add it to ~/.config/story-video-maker/.env"
        )

    model = manifest.voice.model or "gemini-3.1-flash-tts-preview"
    voice = manifest.voice.voice or "Puck"
    response_format = manifest.voice.response_format or "wav"

    for scene in manifest.scenes:
        scene.audio_path = _raw_audio_path(scene.id, response_format)
        out_path = base_dir / scene.audio_path
        if out_path.exists() and not force:
            continue
        out_path.parent.mkdir(parents=True, exist_ok=True)
        _call_gemini_tts(
            api_key=api_key,
            model=model,
            voice=voice,
            text=scene.narration,
            out_path=out_path,
        )
        ffmpeg.probe_duration(out_path)


def generate_gemini_preview(
    manifest: Manifest,
    base_dir: Path,
    text: str | None = None,
    out_path: Path | None = None,
    force: bool = False,
) -> Path:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Add it to ~/.config/story-video-maker/.env"
        )

    model = manifest.voice.model or "gemini-3.1-flash-tts-preview"
    voice = manifest.voice.voice or "Puck"
    preview_text = text or "नमस्ते, आज मैं आपकी क्या मदद कर सकता हूँ?"
    destination = out_path or base_dir / f"audio/previews/{model.replace(':', '-')}-{voice}.wav"
    if destination.exists() and not force:
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    _call_gemini_tts(
        api_key=api_key,
        model=model,
        voice=voice,
        text=preview_text,
        out_path=destination,
    )
    ffmpeg.probe_duration(destination)
    return destination


def _call_gemini_tts(
    *,
    api_key: str,
    model: str,
    voice: str,
    text: str,
    out_path: Path,
) -> None:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [
            {
                "parts": [{"text": text}]
            }
        ],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {
                        "voiceName": voice
                    }
                }
            }
        }
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "story-video-maker/0.1",
        },
        method="POST",
    )

    try:
        ctx = _ssl_context()
    except Exception:
        ctx = ssl._create_unverified_context()

    try:
        try:
            with urllib.request.urlopen(request, timeout=90, context=ctx) as response:
                res_data = json.loads(response.read().decode("utf-8"))
        except ssl.SSLCertVerificationError:
            # Fallback to unverified SSL context if certificate verification fails
            unverified_ctx = ssl._create_unverified_context()
            with urllib.request.urlopen(request, timeout=90, context=unverified_ctx) as response:
                res_data = json.loads(response.read().decode("utf-8"))

        candidates = res_data.get("candidates", [])
        if not candidates:
            raise RuntimeError(f"Gemini TTS response did not contain candidates: {res_data}")
        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            raise RuntimeError(f"Gemini TTS response did not contain parts: {res_data}")
        inline_data = parts[0].get("inlineData", {})
        audio_b64 = inline_data.get("data")
        if not audio_b64:
            raise RuntimeError(f"Gemini TTS response did not contain audio data: {res_data}")

        raw_pcm = base64.b64decode(audio_b64)

        # Gemini returns little-endian PCM despite audio/l16 MIME type — write raw bytes directly
        with wave.open(str(out_path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(24000)
            wav_file.writeframes(raw_pcm)

    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1200]
        raise RuntimeError(f"Gemini TTS request failed with HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Gemini TTS request failed: {exc.reason}") from exc

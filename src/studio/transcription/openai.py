"""OpenAI Whisper transcription fallback with word timestamps."""
from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request
from pathlib import Path

from studio.transcription.groq import build_multipart
from studio.voice.voice import load_env


def load_openai_key() -> str:
    load_env()
    value = os.environ.get("OPENAI_API_KEY") or os.environ.get("openai_api_key") or ""
    return value.strip().strip('"').strip("'")


def extract_timestamps_openai(
    audio_path: Path,
    language: str,
    *,
    api_key: str,
    chunk_label: str = "",
) -> dict:
    """Transcribe one unit using whisper-1 verbose JSON; no audio chunk overlap."""
    fields = {
        "model": "whisper-1",
        "response_format": "verbose_json",
        "timestamp_granularities[]": ["word", "segment"],
        "language": language,
    }
    body, content_type = build_multipart(
        fields,
        {"file": (audio_path.name, audio_path.read_bytes(), "audio/wav")},
    )
    request = urllib.request.Request(
        "https://api.openai.com/v1/audio/transcriptions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": content_type,
            "User-Agent": "story-video-maker/0.1",
        },
        method="POST",
    )
    ctx = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(request, timeout=180, context=ctx) as response:
            raw = json.loads(response.read().decode("utf-8"))
            request_id = response.headers.get("x-request-id")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"OpenAI whisper-1 HTTP {exc.code} [{chunk_label}]: {detail}") from exc

    words = [
        {"word": word.get("word", "").strip(), "start": float(word["start"]), "end": float(word["end"])}
        for word in raw.get("words", [])
    ]
    return {
        "provider": "openai",
        "model": "whisper-1",
        "request_id": request_id,
        "duration": float(raw.get("duration", 0.0)),
        "language": raw.get("language", language),
        "word_count": len(words),
        "words": words,
        "segments": raw.get("segments") or [],
    }

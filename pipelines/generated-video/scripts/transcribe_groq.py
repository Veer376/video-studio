#!/usr/bin/env python3
"""Transcribe project video/audio through Groq Whisper for clip review.

Uses the shared GROQ_API_KEY configuration from ~/.config/projects/.env,
matching the Image Studio transcription convention. No local ASR model is
downloaded or loaded.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import ssl
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


DEFAULT_MODEL = "whisper-large-v3"
DEFAULT_ENV = Path.home() / ".config/projects/.env"


def load_shared_env(path: Path = DEFAULT_ENV) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_groq_keys() -> list[str]:
    keys: list[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        value = value.strip().strip('"').strip("'")
        if value and value not in seen:
            seen.add(value)
            keys.append(value)

    add(os.environ.get("GROQ_API_KEY", ""))
    index = 1
    while True:
        value = os.environ.get(f"GROQ_API_KEY_{index}", "")
        if not value:
            break
        add(value)
        index += 1
    return keys


def extract_review_audio(source: Path, destination: Path) -> Path:
    """Extract deterministic review audio without altering the source media."""
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(source),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(destination),
        ],
        check=True,
    )
    if not destination.is_file() or destination.stat().st_size == 0:
        raise RuntimeError(f"FFmpeg produced no review audio: {destination}")
    return destination


def build_request_body(
    audio_path: Path,
    *,
    language: str,
    model: str,
    prompt: str | None,
) -> tuple[bytes, str]:
    boundary = "----VideoStudioGroqBoundary9f1c2b7a"
    fields: list[tuple[str, str]] = [
        ("model", model),
        ("response_format", "verbose_json"),
        ("timestamp_granularities[]", "word"),
        ("timestamp_granularities[]", "segment"),
        ("language", language),
    ]
    if prompt:
        fields.append(("prompt", prompt[-800:]))

    parts: list[bytes] = []
    for name, value in fields:
        parts.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                f"{value}\r\n"
            ).encode("utf-8")
        )

    mime_type = mimetypes.guess_type(audio_path.name)[0] or "audio/wav"
    parts.append(
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{audio_path.name}"\r\n'
            f"Content-Type: {mime_type}\r\n\r\n"
        ).encode("utf-8")
    )
    parts.append(audio_path.read_bytes())
    parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def transcribe(
    audio_path: Path,
    *,
    language: str,
    model: str = DEFAULT_MODEL,
    prompt: str | None = None,
) -> dict:
    load_shared_env()
    keys = load_groq_keys()
    if not keys:
        raise RuntimeError(
            "No Groq API key configured. Expected GROQ_API_KEY in "
            f"{DEFAULT_ENV}."
        )

    body, content_type = build_request_body(
        audio_path, language=language, model=model, prompt=prompt
    )
    last_error: Exception | None = None
    attempts = max(3, len(keys) * 3)

    for attempt in range(attempts):
        key = keys[attempt % len(keys)]
        request = urllib.request.Request(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            data=body,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": content_type,
                "User-Agent": "video-studio/1.0",
            },
            method="POST",
        )
        try:
            try:
                with urllib.request.urlopen(
                    request, timeout=180, context=ssl.create_default_context()
                ) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.URLError as exc:
                # Match Image Studio's Groq path on local Python installs whose
                # certificate bundle cannot validate the system chain. This is
                # only a transport fallback; the bearer key and HTTPS endpoint
                # remain unchanged.
                if "CERTIFICATE_VERIFY_FAILED" not in str(exc):
                    raise
                with urllib.request.urlopen(
                    request, timeout=180, context=ssl._create_unverified_context()
                ) as response:
                    return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:400]
            last_error = RuntimeError(f"Groq HTTP {exc.code}: {detail}")
            if exc.code not in {429, 500, 502, 503, 504}:
                raise last_error from exc
        except urllib.error.URLError as exc:
            last_error = exc

        if attempt + 1 < attempts:
            time.sleep(min(2 + attempt, 6))

    raise RuntimeError(f"Groq transcription failed after {attempts} attempts: {last_error}")


def normalize_result(raw: dict, source: Path, model: str, language: str) -> dict:
    segments = []
    for segment in raw.get("segments") or []:
        segments.append(
            {
                "start": float(segment.get("start", 0.0)),
                "end": float(segment.get("end", 0.0)),
                "text": str(segment.get("text", "")).strip(),
            }
        )

    words = []
    for word in raw.get("words") or []:
        words.append(
            {
                "start": float(word.get("start", 0.0)),
                "end": float(word.get("end", 0.0)),
                "word": str(word.get("word", "")).strip(),
            }
        )

    return {
        "source": str(source),
        "provider": "groq",
        "model": model,
        "language": language,
        "text": str(raw.get("text", "")).strip(),
        "segments": segments,
        "words": words,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Video or audio file to transcribe")
    parser.add_argument("--language", default="hi", help="Groq language code (default: hi)")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--prompt", default=None, help="Optional short ASR context prompt")
    parser.add_argument("--output", type=Path, help="Optional JSON output path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = args.input.expanduser().resolve()
    if not source.is_file():
        raise SystemExit(f"Input does not exist: {source}")

    with tempfile.TemporaryDirectory(prefix="video-studio-groq-") as temp_dir:
        temp_audio = Path(temp_dir) / "review.wav"
        audio_path = extract_review_audio(source, temp_audio)
        raw = transcribe(
            audio_path,
            language=args.language,
            model=args.model,
            prompt=args.prompt,
        )

    result = normalize_result(raw, source, args.model, args.language)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        output = args.output.expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
        print(output)
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

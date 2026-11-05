"""
Extract word-level timestamps from narration.wav using Groq Whisper.

Usage:
    python3 extract_timestamps.py --project-dir library/2026-08-01_krishna-motivation
"""
import argparse
import json
import os
import sys
import ssl
import time
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from studio.core.http import tls_context


def load_env():
    from studio.core.env import load_env as load_configured_env
    load_configured_env()


def load_groq_keys() -> list[str]:
    """
    Collect all Groq API keys from environment variables.
    Supports: GROQ_API_KEY, GROQ_API_KEY_1, GROQ_API_KEY_2, ..., GROQ_API_KEY_N
    Keys are returned in a deterministic order: base key first, then _1, _2, etc.
    """
    keys = []
    seen = set()

    def _add(val: str) -> None:
        val = val.strip().strip('"').strip("'")
        if val and val not in seen:
            keys.append(val)
            seen.add(val)

    # Base key first
    base = os.environ.get("GROQ_API_KEY", "")
    _add(base)

    # Numbered variants: GROQ_API_KEY_1 ... GROQ_API_KEY_N
    idx = 1
    while True:
        val = os.environ.get(f"GROQ_API_KEY_{idx}", "")
        if not val:
            break
        _add(val)
        idx += 1

    return keys


def build_multipart(fields: dict, files: dict) -> tuple[bytes, str]:
    """Build a multipart/form-data request body manually."""
    boundary = "----StoryVideoMakerBoundary7f3b8a2c"
    body_parts = []

    for name, value in fields.items():
        values = value if isinstance(value, (list, tuple)) else [value]
        for item in values:
            body_parts.append(
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                f"{item}\r\n"
            )

    body = "".join(body_parts).encode("utf-8")
    for name, (filename, data, content_type) in files.items():
        body += (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode("utf-8") + data + b"\r\n"

    body += f"--{boundary}--\r\n".encode("utf-8")
    return body, f"multipart/form-data; boundary={boundary}"


# TODO: Persist successful per-chunk ASR responses so interrupted
# transcription jobs can resume without retranscribing completed chunks.

def extract_timestamps_single(
    audio_path: Path,
    language: str,
    keys: list[str],
    model_name: str = "whisper-large-v3",
    chunk_label: str = "",
    prompt: str | None = None,
) -> dict:
    """
    Call Groq Whisper with verbose_json + word-level timestamps on a single audio file/chunk.

    Key Rotation Strategy:
    - Accepts a pool of Groq API keys (keys).
    - On HTTP 500/429 (rate-limit/server errors), rotates to the next key in the pool.
    - Retries across all keys up to max_attempts times before failing.
    - Never falls back to a lighter model — always uses model_name (whisper-large-v3).
    """
    temp_audio = None
    upload_path = audio_path
    filename = audio_path.name
    mime_type = "audio/wav"

    # Groq accepts WAV directly and downsamples internally. Only reduce files
    # approaching the free-tier upload limit, and keep that conversion lossless.
    if audio_path.stat().st_size > 20 * 1024 * 1024:
        temp_audio = audio_path.parent / f"groq_temp_{audio_path.stem}.flac"
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(audio_path), "-ac", "1", "-ar", "16000", "-c:a", "flac", str(temp_audio)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        upload_path = temp_audio
        filename = "narration.flac"
        mime_type = "audio/flac"

    audio_data = upload_path.read_bytes()
    boundary = "----StoryVideoMakerBoundary7f3b8a2c"

    body_lines = []
    def add_field(name, value):
        body_lines.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n")

    add_field("model", model_name)
    add_field("response_format", "verbose_json")
    add_field("timestamp_granularities[]", "word")
    add_field("timestamp_granularities[]", "segment")
    add_field("language", language)
    if prompt:
        # Groq limits prompts to 896 characters. Preserve the tail because
        # incomplete decodes have been dropping the ends of narration units.
        if len(prompt) > 300:
            prompt = prompt[-300:]
            if " " in prompt:
                prompt = prompt.split(" ", 1)[1]
        add_field("prompt", prompt)

    header = "".join(body_lines).encode("utf-8")
    file_header = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: {mime_type}\r\n\r\n"
    ).encode("utf-8")
    footer = f"\r\n--{boundary}--\r\n".encode("utf-8")

    body = header + file_header + audio_data + footer
    content_type = f"multipart/form-data; boundary={boundary}"
    ctx = tls_context()

    # Key rotation: cycle through all available keys on retryable errors.
    # Never fall back to a lighter model — always use model_name (whisper-large-v3).
    n_keys = max(len(keys), 1)
    max_attempts = n_keys * 3  # Give each key up to 3 chances
    raw = {}
    last_exc = None

    for attempt in range(1, max_attempts + 1):
        key_idx = (attempt - 1) % n_keys
        current_key = keys[key_idx] if keys else ""
        label = chunk_label or upload_path.name

        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            data=body,
            headers={
                "Authorization": f"Bearer {current_key}",
                "Content-Type": content_type,
                "User-Agent": "story-video-maker/0.1",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=180, context=ctx) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
                break
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:400]
            last_exc = exc
            if exc.code in (429, 500, 502, 503, 504):
                next_key_idx = (key_idx + 1) % n_keys
                wait_time = 2 + (attempt % n_keys) * 2  # 2s, 4s, 6s per rotation cycle
                print(
                    f"  Warning: Groq HTTP {exc.code} [{label}] key[{key_idx + 1}/{n_keys}] "
                    f"(attempt {attempt}/{max_attempts}). "
                    f"Rotating to key[{next_key_idx + 1}] in {wait_time}s..."
                )
                time.sleep(wait_time)
                continue
            raise RuntimeError(f"Groq Whisper HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            last_exc = exc
            wait_time = 3
            print(f"  Warning: Groq network error [{label}] (attempt {attempt}/{max_attempts}). Retrying in {wait_time}s...")
            time.sleep(wait_time)
            continue

    if not raw:
        raise RuntimeError(
            f"Groq {model_name} failed after {max_attempts} attempts across {n_keys} key(s): {last_exc}"
        )

    all_words = []
    root_words = raw.get("words")
    if root_words:
        for w in root_words:
            all_words.append({
                "word": w["word"].strip(),
                "start": float(w["start"]),
                "end": float(w["end"]),
            })
    else:
        segments = raw.get("segments") or []
        for segment in segments:
            for w in segment.get("words", []):
                all_words.append({
                    "word": w["word"].strip(),
                    "start": float(w["start"]),
                    "end": float(w["end"]),
                })

    if temp_audio and temp_audio.exists():
        try:
            temp_audio.unlink()
        except Exception:
            pass

    return {
        "duration": float(raw.get("duration", 0.0)),
        "language": raw.get("language", language),
        "word_count": len(all_words),
        "words": all_words,
        "segments": raw.get("segments") or [],
    }


def extract_timestamps(keys: list[str], audio_path: Path, language: str, model_name: str = "whisper-large-v3") -> dict:
    """Transcribe one audio file in one request; unitization is owned upstream."""
    return extract_timestamps_single(audio_path, language, keys=keys, model_name=model_name)


def main():
    parser = argparse.ArgumentParser(description="Extract word timestamps from narration.wav using Groq Whisper")
    parser.add_argument("--project-dir", required=True, help="Path to the project directory")
    parser.add_argument("--force", action="store_true", help="Re-run even if timestamps.json already exists")
    args = parser.parse_args()

    load_env()
    keys = load_groq_keys()
    if not keys:
        print("ERROR: No Groq API keys found. Set GROQ_API_KEY (and optionally GROQ_API_KEY_1, GROQ_API_KEY_2, ...) in the environment or an explicit STUDIO_ENV_FILE", file=sys.stderr)
        sys.exit(1)
    print(f"  Loaded {len(keys)} Groq API key(s) for rotation.")

    project_dir = Path(args.project_dir)
    audio_path = project_dir / "audio" / "narration.wav"
    out_path = project_dir / "audio" / "timestamps.json"
    session_path = project_dir / "session.json"

    if not audio_path.exists():
        print(f"ERROR: narration.wav not found at {audio_path}", file=sys.stderr)
        sys.exit(1)
    if out_path.exists() and not args.force:
        print(f"✓ timestamps.json already exists. Use --force to re-extract.")
        sys.exit(0)

    # Get language from voice config; default to Hindi for the current pipeline.
    language = "hi"
    if session_path.exists():
        session = json.loads(session_path.read_text(encoding="utf-8"))
        lang_code = session.get("voice", {}).get("language", "hi-IN")
        language = lang_code.split("-")[0]  # "hi-IN" → "hi"

    size_mb = audio_path.stat().st_size / (1024 * 1024)
    print(f"→ Extracting timestamps from narration.wav ({size_mb:.1f} MB)")
    print(f"  Model: whisper-large-v3 | Language: {language}")

    result = extract_timestamps(keys=keys, audio_path=audio_path, language=language)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"✓ Timestamps written to: {out_path}")
    print(f"  Duration: {result['duration']:.2f}s | Words: {result['word_count']}")


if __name__ == "__main__":
    main()

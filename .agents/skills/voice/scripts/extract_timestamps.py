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
import urllib.error
import urllib.request
import io
from pathlib import Path


def load_env():
    env_path = Path.home() / ".config/story-video-maker/.env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def build_multipart(fields: dict, files: dict) -> tuple[bytes, str]:
    """Build a multipart/form-data request body manually."""
    boundary = "----StoryVideoMakerBoundary7f3b8a2c"
    body_parts = []

    for name, value in fields.items():
        body_parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n"
        )

    for name, (filename, data, content_type) in files.items():
        body_parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        )
        body_parts_bytes = "".join(body_parts).encode("utf-8") + data + b"\r\n"
        body_parts = []
        body_parts_bytes += f"--{boundary}--\r\n".encode("utf-8")
        return body_parts_bytes, f"multipart/form-data; boundary={boundary}"

    # Only fields, no files
    body = ("".join(body_parts) + f"--{boundary}--\r\n").encode("utf-8")
    return body, f"multipart/form-data; boundary={boundary}"


def extract_timestamps(api_key: str, audio_path: Path, language: str) -> dict:
    """
    Call Groq Whisper with verbose_json + word-level timestamps.

    Returns a dict with keys: duration, language, word_count, words.
    Each word: {"word": str, "start": float, "end": float}
    """
    audio_data = audio_path.read_bytes()
    boundary = "----StoryVideoMakerBoundary7f3b8a2c"

    body_lines = []
    def add_field(name, value):
        body_lines.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n")

    add_field("model", "whisper-large-v3")
    add_field("response_format", "verbose_json")
    add_field("timestamp_granularities[]", "word")
    add_field("language", language)

    header = "".join(body_lines).encode("utf-8")
    file_header = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="narration.wav"\r\n'
        f"Content-Type: audio/wav\r\n\r\n"
    ).encode("utf-8")
    footer = f"\r\n--{boundary}--\r\n".encode("utf-8")

    body = header + file_header + audio_data + footer
    content_type = f"multipart/form-data; boundary={boundary}"

    ctx = ssl._create_unverified_context()

    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/audio/transcriptions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": content_type,
            "User-Agent": "story-video-maker/0.1",
        },
        method="POST",
    )

    try:
        try:
            with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
        except ssl.SSLCertVerificationError:
            unverified = ssl._create_unverified_context()
            with urllib.request.urlopen(req, timeout=120, context=unverified) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:800]
        raise RuntimeError(f"Groq Whisper HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Groq Whisper network error: {exc.reason}") from exc

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

    return {
        "duration": float(raw.get("duration", 0.0)),
        "language": raw.get("language", language),
        "word_count": len(all_words),
        "words": all_words,
    }


def main():
    parser = argparse.ArgumentParser(description="Extract word timestamps from narration.wav using Groq Whisper")
    parser.add_argument("--project-dir", required=True, help="Path to the project directory")
    parser.add_argument("--force", action="store_true", help="Re-run even if timestamps.json already exists")
    args = parser.parse_args()

    load_env()
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        print("ERROR: GROQ_API_KEY not found in environment or ~/.config/story-video-maker/.env", file=sys.stderr)
        sys.exit(1)

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

    # Get language from session.json
    language = "hi"
    if session_path.exists():
        session = json.loads(session_path.read_text(encoding="utf-8"))
        lang_code = session.get("voice", {}).get("language", "hi-IN")
        language = lang_code.split("-")[0]  # "hi-IN" → "hi"

    size_mb = audio_path.stat().st_size / (1024 * 1024)
    print(f"→ Extracting timestamps from narration.wav ({size_mb:.1f} MB)")
    print(f"  Model: whisper-large-v3 | Language: {language}")

    result = extract_timestamps(api_key=api_key, audio_path=audio_path, language=language)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"✓ Timestamps written to: {out_path}")
    print(f"  Duration: {result['duration']:.2f}s | Words: {result['word_count']}")


if __name__ == "__main__":
    main()

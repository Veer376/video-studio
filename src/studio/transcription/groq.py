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
import io
from pathlib import Path


def load_env():
    env_path = Path.home() / ".config/projects/.env"
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


# TODO: Persist successful per-chunk ASR responses so interrupted
# transcription jobs can resume without retranscribing completed chunks.

def extract_timestamps_single(api_key: str, audio_path: Path, language: str, model_name: str = "whisper-large-v3") -> dict:
    """
    Call Groq Whisper with verbose_json + word-level timestamps on a single audio file/chunk.
    """
    temp_mp3 = None
    upload_path = audio_path
    filename = audio_path.name
    mime_type = "audio/wav"

    # Compress large audio files > 5MB to lightweight MP3 (32k mono) to prevent Groq HTTP 500 errors
    if audio_path.stat().st_size > 5 * 1024 * 1024 or audio_path.suffix.lower() == ".wav":
        temp_mp3 = audio_path.parent / f"groq_temp_{audio_path.stem}.mp3"
        subprocess.run(["ffmpeg", "-y", "-i", str(audio_path), "-ac", "1", "-ar", "16000", "-b:a", "32k", str(temp_mp3)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        upload_path = temp_mp3
        filename = "narration.mp3"
        mime_type = "audio/mp3"

    audio_data = upload_path.read_bytes()
    boundary = "----StoryVideoMakerBoundary7f3b8a2c"

    body_lines = []
    def add_field(name, value):
        body_lines.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n")

    add_field("model", model_name)
    add_field("response_format", "verbose_json")
    add_field("timestamp_granularities[]", "word")
    add_field("language", language)

    header = "".join(body_lines).encode("utf-8")
    file_header = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: {mime_type}\r\n\r\n"
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

    max_attempts = 4
    raw = {}
    for attempt in range(1, max_attempts + 1):
        try:
            try:
                with urllib.request.urlopen(req, timeout=180, context=ctx) as resp:
                    raw = json.loads(resp.read().decode("utf-8"))
                    break
            except ssl.SSLCertVerificationError:
                unverified = ssl._create_unverified_context()
                with urllib.request.urlopen(req, timeout=180, context=unverified) as resp:
                    raw = json.loads(resp.read().decode("utf-8"))
                    break
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:800]
            if exc.code in (500, 502, 503, 504):
                if attempt < max_attempts:
                    wait_time = attempt * 3
                    print(f"  Warning: Groq Whisper HTTP {exc.code} on {model_name} (attempt {attempt}/{max_attempts}). Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                elif model_name != "whisper-large-v3-turbo":
                    print(f"  Warning: Groq Whisper HTTP {exc.code} on {model_name}. Falling back to whisper-large-v3-turbo for this chunk...")
                    return extract_timestamps_single(api_key, audio_path, language, model_name="whisper-large-v3-turbo")
            raise RuntimeError(f"Groq Whisper HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            if attempt < max_attempts:
                wait_time = attempt * 3
                print(f"  Warning: Groq Whisper network error {exc.reason} (attempt {attempt}/{max_attempts}). Retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
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

    if temp_mp3 and temp_mp3.exists():
        try:
            temp_mp3.unlink()
        except Exception:
            pass

    return {
        "duration": float(raw.get("duration", 0.0)),
        "language": raw.get("language", language),
        "word_count": len(all_words),
        "words": all_words,
    }


def extract_timestamps(api_key: str, audio_path: Path, language: str, model_name: str = "whisper-large-v3") -> dict:
    """
    Extract timestamps from narration audio using Overlapping Chunked ASR for long audio (> 120s),
    or single pass for short audio (<= 120s).
    """
    # Probe duration
    total_duration = 0.0
    try:
        with wave.open(str(audio_path), "rb") as w:
            total_duration = round(w.getnframes() / w.getframerate(), 2)
    except Exception:
        # Fallback to ffprobe
        res = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
            capture_output=True, text=True, check=True
        )
        total_duration = round(float(res.stdout.strip()), 2)

    # Single pass if <= 120s
    if total_duration <= 120.0:
        return extract_timestamps_single(api_key, audio_path, language, model_name=model_name)

    # Overlapping Chunked ASR for long audio (> 120s)
    chunk_size = 90.0
    overlap = 10.0
    step = chunk_size - overlap

    chunks = []
    curr = 0.0
    while curr < total_duration:
        c_end = min(curr + chunk_size, total_duration)
        # Avoid tiny final chunk <= 10s by extending previous chunk
        if total_duration - curr <= chunk_size + 10.0:
            c_end = total_duration
            chunks.append((round(curr, 2), round(c_end, 2)))
            break
        chunks.append((round(curr, 2), round(c_end, 2)))
        curr += step

    print(f"→ Executing Overlapping Chunked ASR across {len(chunks)} audio chunks ({total_duration}s total)...")

    temp_dir = audio_path.parent / "chunks_temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    all_chunk_words = []
    try:
        for idx, (cs, ce) in enumerate(chunks):
            dur = ce - cs
            chunk_file = temp_dir / f"chunk_{idx+1:02d}.mp3"
            subprocess.run(
                ["ffmpeg", "-y", "-ss", str(cs), "-i", str(audio_path), "-t", str(dur), "-ac", "1", "-ar", "16000", "-b:a", "32k", str(chunk_file)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
            )

            res = extract_timestamps_single(api_key, chunk_file, language, model_name=model_name)
            c_words = res.get("words", [])

            # Convert local timestamps to global
            global_words = []
            for w in c_words:
                global_words.append({
                    "word": w["word"],
                    "start": round(cs + float(w["start"]), 3),
                    "end": round(cs + float(w["end"]), 3)
                })
            all_chunk_words.append(global_words)
            print(f"  ✓ Chunk {idx+1}/{len(chunks)} [{cs}s -> {ce}s]: {len(global_words)} words extracted")
    finally:
        # Clean up temporary chunk files
        for f in temp_dir.glob("*.mp3"):
            try:
                f.unlink()
            except Exception:
                pass
        try:
            temp_dir.rmdir()
        except Exception:
            pass

    # Deduplicate words across overlapping boundaries
    merged = list(all_chunk_words[0]) if all_chunk_words else []
    for c_idx in range(1, len(all_chunk_words)):
        curr_words = all_chunk_words[c_idx]
        if not curr_words:
            continue
        last_merged_end = merged[-1]["end"] if merged else 0.0
        for w in curr_words:
            if w["start"] >= last_merged_end - 0.2:
                if merged and w["word"].strip().lower() == merged[-1]["word"].strip().lower() and abs(w["start"] - merged[-1]["start"]) < 0.5:
                    continue
                merged.append(w)

    return {
        "duration": total_duration,
        "language": language,
        "word_count": len(merged),
        "words": merged,
    }


def main():
    parser = argparse.ArgumentParser(description="Extract word timestamps from narration.wav using Groq Whisper")
    parser.add_argument("--project-dir", required=True, help="Path to the project directory")
    parser.add_argument("--force", action="store_true", help="Re-run even if timestamps.json already exists")
    args = parser.parse_args()

    load_env()
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        print("ERROR: GROQ_API_KEY not found in environment or ~/.config/projects/.env", file=sys.stderr)
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

    # Get language from voice config; default to Hindi for the current pipeline.
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

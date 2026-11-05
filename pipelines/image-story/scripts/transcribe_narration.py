"""
Generate word timestamps for a single concatenated narration file.

The pipeline normally transcribes per-unit (audio/narration/manifest.json) and
stitches offsets in alignment/units.py. This script covers the case where only a
concatenated narration file exists, so timestamps must be derived from the audio
alone.

Two modes:

  chunked (default)
      Cut the audio inside genuine pauses, transcribe each chunk in its own
      whisper-1 request, and offset the words back into absolute file time. This
      mirrors what alignment/units.py does with narration units.

  whole
      One request over the entire file. Kept for comparison and short audio.

Why chunked is the default, and why chunks are small:

  On an 858s file, whole-file whisper-1 returned a near-perfect tail gap (0.03s,
  so no timestamp drift) but silently *skipped* about 17% of the script. One
  skipped 18.2s region, re-transcribed in isolation, returned 51 words of clear
  speech. Long-form Whisper drops audio rather than drifting, and the existing
  coverage validators nearly passed it (82.8% vs a 45% floor).

  At 45s chunks, 4 of 19 chunks still dropped speech; every one of them was
  clean once split to ~22s. Hence the 25s default, which matches the 20-30s
  units the rest of the pipeline already uses.

Cut points matter as much as chunk size: cutting mid-word yields truncated
tokens and makes Whisper skip the head of the next chunk. Cuts are therefore
only placed inside runs of genuinely low energy, never at arithmetic midpoints.

Usage:
    python3 scripts/transcribe_whole.py --project-dir library/koi-tumhe-serious-nahi-leta
"""
from __future__ import annotations

import argparse
import json
import re
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from studio.core.io import read_json, write_json
from studio.transcription.groq import build_multipart
from studio.transcription.openai import load_openai_key
from studio.transcription.units import TRANSCRIPTION_VERSION, validate_transcription
from studio.voice.voice import load_env

# OpenAI rejects transcription uploads above 25 MiB.
MAX_UPLOAD_BYTES = 25 * 1024 * 1024

MIME_BY_SUFFIX = {
    ".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4",
    ".mp4": "audio/mp4", ".flac": "audio/flac", ".ogg": "audio/ogg",
    ".webm": "audio/webm",
}

# Audio a chunk's words leave unaccounted for; the signature of skipped speech.
MAX_INTERNAL_GAP = 2.0
MAX_WORD_SPAN = 3.0
# Whisper sometimes returns slightly intersecting word times within one request.
# Overlaps up to this are repaired in place; anything larger is left visible.
MAX_REPAIRABLE_OVERLAP = 0.6
# Span handed to a word whose timestamps come back zero-width.
MIN_WORD_SPAN = 0.12
RMS_WINDOW = 0.1
# A cut point must sit inside a pause at least this long to avoid splitting a word.
MIN_PAUSE_WINDOWS = 2


# ---------------------------------------------------------------- audio probing

def probe_duration(audio_path: Path) -> float:
    """Read duration from any container; wav_duration() only handles WAV."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


def rms_windows(audio_path: Path) -> list[tuple[float, float]]:
    """Per-window (time, RMS dB). silencedetect reports nothing on this audio at
    any threshold, but the RMS floor drops near -86 dB during pauses, so measure
    it directly instead."""
    result = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(audio_path), "-af",
         f"asetnsamples=n={int(44100 * RMS_WINDOW)},"
         "astats=metadata=1:reset=1,"
         "ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-",
         "-f", "null", "-"],
        capture_output=True, text=True, check=True,
    )
    rows: list[tuple[float, float]] = []
    time_s: float | None = None
    for line in result.stdout.splitlines():
        match = re.search(r"pts_time:([\d.]+)", line)
        if match:
            time_s = float(match.group(1))
            continue
        match = re.search(r"RMS_level=(-?[\d.a-z]+)", line)
        if match and time_s is not None:
            raw = match.group(1)
            rows.append((time_s, -120.0 if "inf" in raw else float(raw)))
    return rows


class PauseMap:
    """Runs of low-energy windows, used to place every cut inside a real pause."""

    def __init__(self, rows: list[tuple[float, float]]) -> None:
        self.rows = rows
        levels = sorted(level for _, level in rows)
        self.threshold = levels[int(len(levels) * 0.20)] if levels else -60.0
        self.pauses: list[tuple[float, float, float]] = []  # (start, end, mean dB)
        run: list[tuple[float, float]] = []
        for row in rows:
            if row[1] <= self.threshold and (not run or abs(row[0] - run[-1][0] - RMS_WINDOW) < 0.02):
                run.append(row)
                continue
            self._flush(run)
            run = [row] if row[1] <= self.threshold else []
        self._flush(run)

    def _flush(self, run: list[tuple[float, float]]) -> None:
        if len(run) >= MIN_PAUSE_WINDOWS:
            self.pauses.append((
                run[0][0],
                run[-1][0] + RMS_WINDOW,
                sum(level for _, level in run) / len(run),
            ))

    def cut_near(self, target: float, *, low: float, high: float, search: float) -> float | None:
        """Centre of the longest pause nearest `target` within the given span.
        Length is preferred over depth: a longer pause is a safer place to cut."""
        for radius in (search, search * 2):
            usable = [
                pause for pause in self.pauses
                if low < (pause[0] + pause[1]) / 2 < high and abs((pause[0] + pause[1]) / 2 - target) <= radius
            ]
            if usable:
                best = max(usable, key=lambda pause: (round(pause[1] - pause[0], 2), -abs((pause[0] + pause[1]) / 2 - target)))
                return round((best[0] + best[1]) / 2, 3)
        return None


def plan_cuts(pause_map: PauseMap, duration: float, *, target: float, search: float) -> list[float]:
    points = [0.0]
    while duration - points[-1] > target * 1.5:
        cut = pause_map.cut_near(
            points[-1] + target,
            low=points[-1] + target * 0.4,
            high=min(points[-1] + target * 2.0, duration - target * 0.4),
            search=search,
        )
        if cut is None or cut <= points[-1] + 1.0:
            # No pause available; extend the current chunk rather than cut into speech.
            cut = min(points[-1] + target * 2.0, duration)
            if cut >= duration - 1.0:
                break
        points.append(cut)
    points.append(round(duration, 3))
    return points


def cut_chunk(audio_path: Path, start: float, end: float, out_path: Path) -> None:
    """Decode to 16 kHz mono WAV: sample-exact (no encoder padding to shift
    offsets) and Whisper's native rate, so nothing is lost."""
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.3f}", "-accurate_seek",
         "-i", str(audio_path), "-t", f"{end - start:.3f}",
         "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(out_path)],
        check=True,
    )


# ------------------------------------------------------------------ openai call

def transcribe_file(audio_path: Path, language: str, *, api_key: str, timeout: int) -> dict:
    """One whisper-1 verbose_json request with word timestamps."""
    size = audio_path.stat().st_size
    if size > MAX_UPLOAD_BYTES:
        raise RuntimeError(
            f"{audio_path.name} is {size / 1048576:.2f} MB, over the 25 MiB upload cap. "
            "Lower --target-chunk, or re-encode at a lower bitrate."
        )
    mime = MIME_BY_SUFFIX.get(audio_path.suffix.lower())
    if mime is None:
        raise RuntimeError(f"Unsupported audio container: {audio_path.suffix}")

    body, content_type = build_multipart(
        {"model": "whisper-1", "response_format": "verbose_json",
         "timestamp_granularities[]": ["word", "segment"], "language": language},
        {"file": (audio_path.name, audio_path.read_bytes(), mime)},
    )
    request = urllib.request.Request(
        "https://api.openai.com/v1/audio/transcriptions",
        data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": content_type,
                 "User-Agent": "story-video-maker/0.1"},
        method="POST",
    )

    def send(context=None):
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            return json.loads(response.read().decode("utf-8")), response.headers.get("x-request-id")

    try:
        raw, request_id = send()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"OpenAI whisper-1 HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        if not isinstance(exc.reason, ssl.SSLError):
            raise
        print("    Warning: TLS verification failed, retrying without verification")
        raw, request_id = send(ssl._create_unverified_context())

    words = [
        {"word": word.get("word", "").strip(),
         "start": round(float(word["start"]), 3),
         "end": round(float(word["end"]), 3)}
        for word in raw.get("words", [])
    ]
    return {
        "provider": "openai", "model": "whisper-1", "request_id": request_id,
        "duration": float(raw.get("duration", 0.0)),
        "language": raw.get("language", language),
        "word_count": len(words), "words": words,
        "segments": raw.get("segments") or [],
    }


# ------------------------------------------------------------------ chunk audit

def coverage_defects(words: list[dict], start: float, end: float) -> list[str]:
    """Audio in [start, end) that no word accounts for, plus implausible spans."""
    if not words:
        return [f"no words for {start:.1f}-{end:.1f}s"]
    reasons = []
    lead = float(words[0]["start"]) - start
    if lead > MAX_INTERNAL_GAP:
        reasons.append(f"{lead:.1f}s uncovered from {start:.1f}s")
    tail = end - float(words[-1]["end"])
    if tail > MAX_INTERNAL_GAP:
        reasons.append(f"{tail:.1f}s uncovered before {end:.1f}s")
    for index in range(1, len(words)):
        gap = float(words[index]["start"]) - float(words[index - 1]["end"])
        if gap > MAX_INTERNAL_GAP:
            reasons.append(f"{gap:.1f}s gap at {words[index - 1]['end']:.1f}s")
    for index, word in enumerate(words):
        span = float(word["end"]) - float(word["start"])
        if span > MAX_WORD_SPAN:
            reasons.append(f"word {index + 1} ({word['word']!r}) spans {span:.1f}s")
    return reasons


def shift(words: list[dict], offset: float) -> list[dict]:
    """Offset into absolute time. Spans are preserved rather than clamped to the
    chunk end: clamping collapsed the final word of every chunk to zero length."""
    return [
        {"word": word["word"],
         "start": round(offset + float(word["start"]), 3),
         "end": round(offset + float(word["end"]), 3)}
        for word in words
    ]


def repair_zero_spans(words: list[dict]) -> tuple[list[dict], int]:
    """Give whisper's zero-width words a usable span. whisper-1 sometimes emits
    start == end for short function words; a zero-duration subtitle cue is not
    renderable, so borrow time up to the next word without displacing it."""
    repaired = [dict(word) for word in words]
    fixes = 0
    for index, word in enumerate(repaired):
        start = float(word["start"])
        if float(word["end"]) > start:
            continue
        # These words usually sit at the same instant as the word after them,
        # with the pause they were spoken in lying just before, so try to grow
        # forward first and fall back to reclaiming that pause.
        ceiling = float(repaired[index + 1]["start"]) if index + 1 < len(repaired) else start + MIN_WORD_SPAN
        floor = float(repaired[index - 1]["end"]) if index else max(0.0, start - MIN_WORD_SPAN)
        if ceiling - start >= 0.001:
            word["end"] = round(min(start + MIN_WORD_SPAN, ceiling), 3)
            fixes += 1
        elif start - floor >= 0.001:
            word["start"] = round(max(start - MIN_WORD_SPAN, floor), 3)
            fixes += 1
    return repaired, fixes


def repair_monotonic(words: list[dict]) -> tuple[list[dict], int]:
    """Nudge small intersecting word times forward. whisper-1 emits these within
    a single request, and validate_transcription rejects non-monotonic output."""
    repaired: list[dict] = []
    fixes = 0
    for word in words:
        if repaired:
            previous_end = float(repaired[-1]["end"])
            if 0 < previous_end - float(word["start"]) <= MAX_REPAIRABLE_OVERLAP:
                word = dict(word)
                word["start"] = round(previous_end, 3)
                word["end"] = round(max(float(word["end"]), previous_end), 3)
                fixes += 1
        repaired.append(word)
    return repaired, fixes


def transcribe_range(
    audio_path: Path, start: float, end: float, language: str, *,
    api_key: str, timeout: int, work_dir: Path, label: str,
    attempts: int, pause_map: PauseMap, depth: int, max_depth: int,
) -> tuple[list[dict], list[dict]]:
    """Transcribe [start, end) and return (absolute words, provider records).

    Whisper is non-deterministic, so a range that drops speech is retried before
    being split. Splits go inside a pause, never at an arithmetic midpoint.
    """
    chunk_path = work_dir / f"{label}.wav"
    cut_chunk(audio_path, start, end, chunk_path)
    chunk_duration = probe_duration(chunk_path)

    best: dict | None = None
    best_reasons: list[str] = ["not attempted"]
    for attempt in range(1, attempts + 1):
        result = transcribe_file(chunk_path, language, api_key=api_key, timeout=timeout)
        reasons = coverage_defects(result["words"], 0.0, chunk_duration)
        if not reasons:
            best, best_reasons = result, []
            break
        if best is None or len(reasons) < len(best_reasons):
            best, best_reasons = result, reasons
        print(f"    {label} attempt {attempt}/{attempts} rejected: {'; '.join(reasons[:3])}")
    chunk_path.unlink(missing_ok=True)

    if best_reasons and depth < max_depth and chunk_duration > 12.0:
        middle = pause_map.cut_near(
            start + (end - start) / 2,
            low=start + 4.0, high=end - 4.0, search=(end - start) / 3,
        )
        if middle is not None:
            print(f"    {label}: splitting at pause {middle:.2f}s")
            left = transcribe_range(
                audio_path, start, middle, language, api_key=api_key, timeout=timeout,
                work_dir=work_dir, label=f"{label}a", attempts=attempts,
                pause_map=pause_map, depth=depth + 1, max_depth=max_depth,
            )
            right = transcribe_range(
                audio_path, middle, end, language, api_key=api_key, timeout=timeout,
                work_dir=work_dir, label=f"{label}b", attempts=attempts,
                pause_map=pause_map, depth=depth + 1, max_depth=max_depth,
            )
            return left[0] + right[0], left[1] + right[1]
        print(f"    {label}: no pause available to split on, keeping best attempt")

    words = shift(best["words"], start)
    status = "ok" if not best_reasons else f"kept with defects: {'; '.join(best_reasons[:2])}"
    print(f"    {label}: {len(words)} words, {status}")
    return words, [{
        "id": label, "provider": best["provider"], "model": best["model"],
        "request_id": best["request_id"], "start": round(start, 3), "end": round(end, 3),
        "word_count": len(words), "defects": best_reasons,
    }]


# ------------------------------------------------------------------------ script

def narration_text(script_path: Path) -> str:
    """Drop markdown headings so expected word counts reflect spoken prose only."""
    lines = script_path.read_text(encoding="utf-8").splitlines()
    return "\n".join(line for line in lines if not line.lstrip().startswith("#")).strip()


def latest_script(project_dir: Path) -> Path | None:
    candidates = sorted(
        (path for path in project_dir.glob("script-v*.md") if "review" not in path.stem),
        key=lambda path: int("".join(ch for ch in path.stem.split("-v")[-1] if ch.isdigit()) or 0),
    )
    return candidates[-1] if candidates else None


# --------------------------------------------------------------------------- cli

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--audio", default="audio/narration.mp3", help="Relative to --project-dir")
    parser.add_argument("--out", default="audio/timestamps.json", help="Relative to --project-dir")
    parser.add_argument("--script", default=None, help="Relative to --project-dir; defaults to the highest script-vN.md")
    parser.add_argument("--language", default=None, help="Defaults to session.json voice language, else 'hi'")
    parser.add_argument("--mode", choices=("chunked", "whole"), default="chunked")
    parser.add_argument("--target-chunk", type=float, default=25.0, help="Seconds per chunk; 45s measurably dropped speech")
    parser.add_argument("--search", type=float, default=6.0, help="Seconds to search around a target for a pause")
    parser.add_argument("--attempts", type=int, default=2, help="Retries before splitting a chunk")
    parser.add_argument("--max-depth", type=int, default=2, help="Maximum recursive splits per chunk")
    parser.add_argument("--timeout", type=int, default=900, help="Seconds per request")
    parser.add_argument("--force", action="store_true", help="Overwrite existing output")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    audio_path = project_dir / args.audio
    out_path = project_dir / args.out
    if not audio_path.exists():
        print(f"ERROR: audio not found at {audio_path}", file=sys.stderr)
        return 1
    if out_path.exists() and not args.force:
        print(f"✓ {args.out} already exists. Use --force to re-extract.")
        return 0

    load_env()
    api_key = load_openai_key()
    if not api_key:
        print("ERROR: OPENAI_API_KEY not found in ~/.config/projects/.env", file=sys.stderr)
        return 1

    language = args.language
    if language is None:
        session_path = project_dir / "session.json"
        language = "hi"
        if session_path.exists():
            language = read_json(session_path).get("voice", {}).get("language", "hi-IN").split("-")[0]

    duration = probe_duration(audio_path)
    print(f"→ {args.mode} transcription: {audio_path.name} "
          f"({audio_path.stat().st_size / 1048576:.2f} MB, {duration:.2f}s)")
    print(f"  Model: whisper-1 | Language: {language}")

    work_dir = project_dir / "audio" / "transcription"
    work_dir.mkdir(parents=True, exist_ok=True)

    if args.mode == "whole":
        result = transcribe_file(audio_path, language, api_key=api_key, timeout=args.timeout)
        words = result["words"]
        units = [{"id": "whole", "provider": result["provider"], "model": result["model"],
                  "request_id": result["request_id"], "start": 0.0, "end": round(duration, 3),
                  "word_count": result["word_count"],
                  "defects": coverage_defects(words, 0.0, duration)}]
        out_language = result["language"]
    else:
        print("  Measuring energy to place cuts inside pauses...")
        pause_map = PauseMap(rms_windows(audio_path))
        points = plan_cuts(pause_map, duration, target=args.target_chunk, search=args.search)
        print(f"  Pause threshold {pause_map.threshold:.1f} dB | {len(pause_map.pauses)} pauses found")
        print(f"  {len(points) - 1} chunk(s), "
              f"{min(points[i+1]-points[i] for i in range(len(points)-1)):.1f}-"
              f"{max(points[i+1]-points[i] for i in range(len(points)-1)):.1f}s each")
        words, units = [], []
        for index in range(len(points) - 1):
            chunk_words, chunk_units = transcribe_range(
                audio_path, points[index], points[index + 1], language,
                api_key=api_key, timeout=args.timeout, work_dir=work_dir,
                label=f"chunk-{index + 1:03d}", attempts=args.attempts,
                pause_map=pause_map, depth=0, max_depth=args.max_depth,
            )
            words.extend(chunk_words)
            units.extend(chunk_units)
        out_language = language

    words.sort(key=lambda word: (word["start"], word["end"]))
    words, fixes = repair_monotonic(words)
    words, span_fixes = repair_zero_spans(words)

    print(f"\n  Words: {len(words)} | last word ends at "
          f"{float(words[-1]['end']) if words else 0:.2f}s of {duration:.2f}s")
    if fixes:
        print(f"  Repaired {fixes} intersecting word time(s)")
    if span_fixes:
        print(f"  Widened {span_fixes} zero-width word span(s)")
    zero_spans = sum(1 for word in words if float(word["end"]) <= float(word["start"]))
    if zero_spans:
        print(f"  WARNING: {zero_spans} zero-length word span(s) remain")
    remaining = coverage_defects(words, 0.0, duration)
    if remaining:
        print(f"  Uncovered audio remaining: {len(remaining)} region(s)")
        for reason in remaining[:10]:
            print(f"    - {reason}")
    else:
        print("  Full audio coverage: no unaccounted region over "
              f"{MAX_INTERNAL_GAP:.0f}s")

    payload = {
        "duration": round(duration, 3), "language": out_language,
        "word_count": len(words), "words": words, "units": units,
        "transcription_version": TRANSCRIPTION_VERSION,
    }

    script_path = (project_dir / args.script) if args.script else latest_script(project_dir)
    if script_path and script_path.exists():
        valid, reasons = validate_transcription(payload, narration_text(script_path), duration)
        print(f"  Validation against {script_path.name}: {'PASS' if valid else 'FAIL'}")
        for reason in reasons[:10]:
            print(f"    - {reason}")
    else:
        print("  Validation skipped: no script found to compare against")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(out_path, payload)
    print(f"✓ Timestamps written to: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

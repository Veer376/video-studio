"""Transcribe durable narration units with validated provider fallback."""
from __future__ import annotations

import copy
from pathlib import Path

from studio.alignment.base import bigram_similarity, content_words, normalize_for_match
from studio.core.io import read_json, write_json
from studio.transcription.groq import extract_timestamps_single, load_groq_keys
from studio.transcription.openai import extract_timestamps_openai, load_openai_key
from studio.voice.units import wav_duration
from studio.voice.voice import load_env


TRANSCRIPTION_VERSION = 1
GROQ_QUALITY_ATTEMPTS = 3


def _fuzzy_lcs_coverage(expected_text: str, actual_words: list[dict]) -> float:
    expected = [normalize_for_match(word) for word in content_words(expected_text)]
    actual = [normalize_for_match(word.get("word", "")) for word in actual_words]
    expected = [word for word in expected if word]
    actual = [word for word in actual if word]
    if not expected or not actual:
        return 0.0
    previous = [0] * (len(actual) + 1)
    for expected_word in expected:
        current = [0]
        for index, actual_word in enumerate(actual, start=1):
            if bigram_similarity(expected_word, actual_word) >= 0.5:
                current.append(previous[index - 1] + 1)
            else:
                current.append(max(previous[index], current[-1]))
        previous = current
    return previous[-1] / len(expected)


def validate_transcription(transcription: dict, expected_text: str, duration: float) -> tuple[bool, list[str]]:
    """Reject truncated or malformed timestamps before they reach alignment."""
    reasons: list[str] = []
    words = list(transcription.get("words") or [])
    if not words:
        return False, ["no words"]

    previous_end = 0.0
    for index, word in enumerate(words):
        try:
            start = float(word["start"])
            end = float(word["end"])
        except (KeyError, TypeError, ValueError):
            reasons.append(f"word {index + 1} has invalid timestamps")
            continue
        if start < previous_end - 0.15 or end < start:
            reasons.append(f"word {index + 1} is non-monotonic")
        if end > duration + 1.0:
            reasons.append(f"word {index + 1} exceeds audio duration")
        if end - start > 3.0:
            reasons.append(f"word {index + 1} spans more than 3 seconds")
        previous_end = max(previous_end, end)

    tail_gap = duration - float(words[-1].get("end", 0.0))
    if tail_gap > max(2.0, duration * 0.10):
        reasons.append(f"transcript ends {tail_gap:.2f}s before audio")

    expected_count = max(1, len(content_words(expected_text)))
    count_ratio = len(words) / expected_count
    if count_ratio < 0.60:
        reasons.append(f"word-count coverage is {count_ratio:.0%}")
    semantic_coverage = _fuzzy_lcs_coverage(expected_text, words)
    if semantic_coverage < 0.45:
        reasons.append(f"ordered text coverage is {semantic_coverage:.0%}")
    return not reasons, reasons


def _validated_copy(result: dict, *, provider: str, model: str, input_hash: str) -> dict:
    output = copy.deepcopy(result)
    output["provider"] = provider
    output["model"] = model
    output["input_hash"] = input_hash
    output["transcription_version"] = TRANSCRIPTION_VERSION
    return output


def transcribe_units(
    project_dir: str | Path,
    *,
    force: bool = False,
    unit_id: str | None = None,
) -> list[dict]:
    """Transcribe selected units: Groq Large V3 first, OpenAI whisper-1 on quality failure."""
    project_dir = Path(project_dir).resolve()
    manifest_path = project_dir / "audio" / "narration" / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError("transcription requires audio/narration/manifest.json")
    units = list(read_json(manifest_path).get("units") or [])
    if unit_id:
        units = [unit for unit in units if unit.get("id") == unit_id]
        if not units:
            raise ValueError(f"Unknown narration unit: {unit_id}")

    load_env()
    groq_keys = load_groq_keys()
    openai_key = load_openai_key()
    if not groq_keys and not openai_key:
        raise RuntimeError("No Groq or OpenAI transcription API key found")

    session_path = project_dir / "session.json"
    language = "hi"
    if session_path.exists():
        language = read_json(session_path).get("voice", {}).get("language", "hi-IN").split("-")[0]

    output_dir = project_dir / "audio" / "transcription"
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    print(f"→ Transcription: {len(units)} unit(s), no overlapping windows")
    for unit in units:
        identifier = unit["id"]
        audio_path = project_dir / unit["audio_path"]
        output_path = output_dir / f"{identifier}.json"
        duration = wav_duration(audio_path)
        if not force and output_path.exists():
            existing = read_json(output_path)
            valid, _ = validate_transcription(existing, unit["text"], duration)
            if (
                valid
                and existing.get("input_hash") == unit["input_hash"]
                and existing.get("transcription_version") == TRANSCRIPTION_VERSION
            ):
                print(f"  {identifier}: reusing {existing.get('provider')} transcription")
                results.append(existing)
                continue

        result: dict | None = None
        if groq_keys:
            for attempt in range(1, GROQ_QUALITY_ATTEMPTS + 1):
                try:
                    candidate = extract_timestamps_single(
                        audio_path,
                        language,
                        keys=groq_keys,
                        model_name="whisper-large-v3",
                        chunk_label=f"{identifier}-quality-{attempt}",
                        prompt=unit["text"],
                    )
                except Exception as exc:
                    print(f"  {identifier}: Groq request failed: {exc}")
                    break
                valid, reasons = validate_transcription(candidate, unit["text"], duration)
                if valid:
                    result = _validated_copy(
                        candidate,
                        provider="groq",
                        model="whisper-large-v3",
                        input_hash=unit["input_hash"],
                    )
                    break
                print(f"  {identifier}: Groq quality attempt {attempt}/3 rejected: {', '.join(reasons)}")

        if result is None:
            if not openai_key:
                raise RuntimeError(f"{identifier}: Groq output invalid and OPENAI_API_KEY is unavailable")
            print(f"  {identifier}: falling back to OpenAI whisper-1")
            candidate = extract_timestamps_openai(
                audio_path,
                language,
                api_key=openai_key,
                chunk_label=identifier,
            )
            valid, reasons = validate_transcription(candidate, unit["text"], duration)
            if not valid:
                raise RuntimeError(f"{identifier}: OpenAI whisper-1 output invalid: {', '.join(reasons)}")
            result = _validated_copy(
                candidate,
                provider="openai",
                model="whisper-1",
                input_hash=unit["input_hash"],
            )

        write_json(output_path, result)
        results.append(result)
        print(f"  ✓ {identifier}: {result['provider']}/{result['model']} ({result['word_count']} words)")
    return results

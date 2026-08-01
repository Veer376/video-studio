"""Shared utilities for all audio providers.

Exports:
    _load_env_keys          — load API keys from ~/.config/story-video-maker/.env
    _raw_audio_path         — compute the relative path for a scene's raw audio file
    _atempo_chain           — build an ffmpeg atempo filter chain for safe tempo adjustment
    _ssl_context            — create an SSL context with CA detection
    estimate_placeholder_duration — estimate a reasonable audio duration from narration text
    measure_scene_audio     — populate scene.duration_seconds from existing audio files
    pace_narration_audio    — apply atempo pacing to raw TTS audio
    validate_existing_audio — verify all scene audio paths exist and are probeable
    generate_voice_preview  — dispatch to provider-specific preview generation
    set_voice_gender        — set the manifest voice to the configured gender default
"""
from __future__ import annotations

import math
import os
import ssl
from pathlib import Path

import ffmpeg
from models import Manifest


# ── Environment loading ───────────────────────────────────────────────────────

def _load_env_keys() -> None:
    """Load API keys from the namespaced XDG config file and the project-local .env.

    Priority order (first match wins, already-set env vars are never overwritten):
      1. ~/.config/story-video-maker/.env  — project-scoped, outside the repo, never committed.
      2. <project_root>/.env               — optional local override (gitignored).
    """
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    candidates = [
        Path.home() / ".config" / "story-video-maker" / ".env",
        project_root / ".env",
    ]
    for env_path in candidates:
        if not env_path.exists():
            continue
        try:
            for raw_line in env_path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = val
        except Exception:
            pass  # never crash the pipeline due to a missing or malformed .env


_load_env_keys()


def load_gemini_api_keys() -> list[str]:
    """Load and deduplicate all Gemini API keys sequentially from the environment.
    
    Checks GEMINI_API_KEY_1 first, falling back to GEMINI_API_KEY if GEMINI_API_KEY_1
    is not set. Then checks GEMINI_API_KEY_2, GEMINI_API_KEY_3, etc. sequentially,
    stopping at the first missing index.
    """
    keys = []
    k1 = os.environ.get("GEMINI_API_KEY_1") or os.environ.get("GEMINI_API_KEY")
    if k1:
        keys.append(k1)
        
    idx = 2
    while True:
        k_n = os.environ.get(f"GEMINI_API_KEY_{idx}")
        if not k_n:
            break
        if k_n not in keys:
            keys.append(k_n)
        idx += 1
        
    return keys


# ── Path helpers ──────────────────────────────────────────────────────────────

def _raw_audio_path(scene_id: str, response_format: str | None = "wav") -> str:
    extension = "wav" if response_format == "mulaw" else (response_format or "wav")
    return f"audio/{scene_id}.{extension}"


# ── Audio duration estimation ─────────────────────────────────────────────────

def estimate_placeholder_duration(text: str) -> float:
    devanagari_chars = sum(1 for char in text if "\u0900" <= char <= "\u097f")
    return max(5.0, min(12.0, 2.2 + devanagari_chars / 13.5))


# ── Scene audio measurement ───────────────────────────────────────────────────

def measure_scene_audio(manifest: Manifest, base_dir: Path) -> None:
    for scene in manifest.scenes:
        if not scene.audio_path:
            continue
        duration = ffmpeg.probe_duration(base_dir / scene.audio_path)
        scene.duration_seconds = round(duration, 3)
        if not math.isfinite(duration) or duration <= 0:
            scene.errors.append("Invalid audio duration")


# ── Pacing ────────────────────────────────────────────────────────────────────

def pace_narration_audio(manifest: Manifest, base_dir: Path, force: bool = False) -> None:
    for scene in manifest.scenes:
        source_rel = _raw_audio_path(scene.id, manifest.voice.response_format)
        source_path = base_dir / source_rel
        if not source_path.exists():
            if not scene.audio_path:
                raise FileNotFoundError(f"{scene.id}: missing audio_path")
            source_path = base_dir / scene.audio_path
        if not source_path.exists():
            raise FileNotFoundError(f"{scene.id}: audio not found: {source_path}")
        source_duration = ffmpeg.probe_duration(source_path)
        target_duration = max(source_duration, estimate_placeholder_duration(scene.narration))
        paced_rel = f"audio/paced/{scene.id}.wav"
        paced_path = base_dir / paced_rel
        if paced_path.exists() and not force:
            scene.audio_path = paced_rel
            scene.duration_seconds = round(ffmpeg.probe_duration(paced_path), 3)
            continue
        paced_path.parent.mkdir(parents=True, exist_ok=True)
        tempo = source_duration / target_duration
        ffmpeg.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(source_path),
                "-af",
                ",".join(_atempo_chain(tempo)),
                "-c:a",
                "pcm_s16le",
                str(paced_path),
            ]
        )
        scene.audio_path = paced_rel
        scene.duration_seconds = round(ffmpeg.probe_duration(paced_path), 3)


def _atempo_chain(tempo: float) -> list[str]:
    if tempo <= 0:
        raise ValueError("Audio tempo must be positive")
    filters: list[str] = []
    while tempo < 0.5:
        filters.append("atempo=0.5")
        tempo /= 0.5
    while tempo > 2.0:
        filters.append("atempo=2.0")
        tempo /= 2.0
    filters.append(f"atempo={tempo:.6f}")
    return filters


# ── Validation ────────────────────────────────────────────────────────────────

def validate_existing_audio(manifest: Manifest, base_dir: Path) -> None:
    for scene in manifest.scenes:
        if not scene.audio_path:
            raise FileNotFoundError(f"{scene.id}: missing audio_path")
        path = base_dir / scene.audio_path
        if not path.exists():
            raise FileNotFoundError(f"{scene.id}: audio not found: {scene.audio_path}")
        ffmpeg.probe_duration(path)


# ── Voice gender helper ───────────────────────────────────────────────────────

def set_voice_gender(manifest: Manifest, gender: str) -> None:
    if manifest.voice.provider not in ("sarvam_tts", "gemini_tts"):
        raise ValueError("--voice-gender is supported only for sarvam_tts and gemini_tts")
    if manifest.voice.provider == "sarvam_tts":
        if gender == "male":
            manifest.voice.voice = manifest.voice.male_voice or "gokul"
            return
        if gender == "female":
            manifest.voice.voice = manifest.voice.female_voice or "priya"
            return
    elif manifest.voice.provider == "gemini_tts":
        if gender == "male":
            manifest.voice.voice = manifest.voice.male_voice or "Puck"
            return
        if gender == "female":
            manifest.voice.voice = manifest.voice.female_voice or "Aoede"
            return
    raise ValueError(f"Unsupported voice gender: {gender}")


# ── Preview dispatcher ────────────────────────────────────────────────────────

def generate_voice_preview(
    manifest: Manifest,
    base_dir: Path,
    text: str | None = None,
    out_path: Path | None = None,
    force: bool = False,
) -> Path:
    if manifest.voice.provider == "groq_tts":
        from .groq import generate_groq_preview
        return generate_groq_preview(manifest, base_dir, text=text, out_path=out_path, force=force)
    if manifest.voice.provider == "sarvam_tts":
        from .sarvam import generate_sarvam_preview
        return generate_sarvam_preview(manifest, base_dir, text=text, out_path=out_path, force=force)
    if manifest.voice.provider == "gemini_tts":
        from .gemini import generate_gemini_preview
        return generate_gemini_preview(manifest, base_dir, text=text, out_path=out_path, force=force)
    raise ValueError(f"voice-preview is not supported for provider: {manifest.voice.provider}")


# ── SSL helpers ───────────────────────────────────────────────────────────────

def _ssl_context() -> ssl.SSLContext:
    cafile = _detect_ca_file()
    if cafile:
        return ssl.create_default_context(cafile=str(cafile))
    return ssl.create_default_context()


def _detect_ca_file() -> Path | None:
    env_path = os.environ.get("SSL_CERT_FILE")
    candidates = [
        Path(env_path) if env_path else None,
        Path("/opt/homebrew/etc/ca-certificates/cert.pem"),
        Path("/opt/homebrew/etc/openssl@3/cert.pem"),
        Path("/etc/ssl/cert.pem"),
    ]
    try:
        import certifi  # type: ignore
        candidates.insert(1, Path(certifi.where()))
    except ImportError:
        pass
    return next((path for path in candidates if path and path.exists()), None)

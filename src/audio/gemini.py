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
from .base import _raw_audio_path, _ssl_context, load_gemini_api_keys


def generate_gemini_audio(manifest: Manifest, base_dir: Path, force: bool = False) -> None:
    api_keys = load_gemini_api_keys()
    if not api_keys:
        raise RuntimeError(
            "No Gemini API keys found. Set GEMINI_API_KEY or GEMINI_API_KEY_1 in your environment."
        )

    model = manifest.voice.model or "gemini-3.1-flash-tts-preview"
    voice = manifest.voice.voice or "Puck"
    response_format = manifest.voice.response_format or "wav"

    for idx, scene in enumerate(manifest.scenes):
        scene.audio_path = _raw_audio_path(scene.id, response_format)
        out_path = base_dir / scene.audio_path
        if out_path.exists() and not force:
            continue
        out_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Use round-robin key rotation across scenes
        api_key = api_keys[idx % len(api_keys)]
        
        _call_gemini_tts(
            api_key=api_key,
            model=model,
            voice=voice,
            text=scene.narration,
            out_path=out_path,
            scene_id=scene.id,
            base_dir=base_dir,
        )
        ffmpeg.probe_duration(out_path)


def generate_gemini_preview(
    manifest: Manifest,
    base_dir: Path,
    text: str | None = None,
    out_path: Path | None = None,
    force: bool = False,
) -> Path:
    api_keys = load_gemini_api_keys()
    if not api_keys:
        raise RuntimeError(
            "No Gemini API keys found. Set GEMINI_API_KEY or GEMINI_API_KEY_1 in your environment."
        )
    
    # Use the first available key for preview
    api_key = api_keys[0]

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
        scene_id=None,
        base_dir=base_dir,
    )
    ffmpeg.probe_duration(destination)
    return destination


def _log_error_to_disk(
    base_dir: Path,
    scene_id: str | None,
    error_type: str,
    status_code: int | None,
    message: str,
    detail: str | None,
    api_key: str,
    attempt: int,
) -> None:
    from datetime import datetime
    import sys
    try:
        errors_dir = base_dir / "errors" / "audio"
        errors_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = scene_id if scene_id else "preview"
        log_file = errors_dir / f"{prefix}_{timestamp}.json"
        
        # Mask the api key for safety
        masked_key = "N/A"
        if api_key:
            if len(api_key) > 8:
                masked_key = f"{api_key[:4]}...{api_key[-4:]}"
            else:
                masked_key = "..."
                
        payload = {
            "scene_id": scene_id,
            "error_type": error_type,
            "status_code": status_code,
            "message": message,
            "detail": detail,
            "api_key_masked": masked_key,
            "attempts": attempt,
            "timestamp": datetime.now().isoformat()
        }
        
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
            
    except Exception as e:
        print(f"Warning: Failed to log error to disk: {e}", file=sys.stderr)


def _call_gemini_tts(
    *,
    api_key: str,
    model: str,
    voice: str,
    text: str,
    out_path: Path,
    scene_id: str | None,
    base_dir: Path,
) -> None:
    import time
    import sys
    
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

    max_retries = 5
    backoff_base = 2.0  # seconds

    for attempt in range(1, max_retries + 1):
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
            
            return  # Success, exit the retry loop

        except urllib.error.HTTPError as exc:
            status_code = exc.code
            detail = exc.read().decode("utf-8", errors="replace")[:1200]
            
            # 429, 499, 500, 503, 504 are retryable
            retryable_codes = {429, 499, 500, 503, 504}
            if status_code in retryable_codes and attempt < max_retries:
                wait_time = backoff_base * (2 ** (attempt - 1))
                print(f"Gemini TTS request failed with HTTP {status_code} (attempt {attempt}/{max_retries}). Retrying in {wait_time:.1f}s...", file=sys.stderr)
                time.sleep(wait_time)
                continue
                
            # Log fatal error or exhausted retry to disk
            _log_error_to_disk(
                base_dir=base_dir,
                scene_id=scene_id,
                error_type="HTTPError",
                status_code=status_code,
                message=str(exc),
                detail=detail,
                api_key=api_key,
                attempt=attempt,
            )
            raise RuntimeError(f"Gemini TTS request failed with HTTP {status_code}: {detail}") from exc

        except urllib.error.URLError as exc:
            # Network issue, SSL error, DNS failure, etc. — retryable
            if attempt < max_retries:
                wait_time = backoff_base * (2 ** (attempt - 1))
                print(f"Gemini TTS request failed: {exc.reason} (attempt {attempt}/{max_retries}). Retrying in {wait_time:.1f}s...", file=sys.stderr)
                time.sleep(wait_time)
                continue
                
            # Log final failure to disk
            _log_error_to_disk(
                base_dir=base_dir,
                scene_id=scene_id,
                error_type="URLError",
                status_code=None,
                message=str(exc),
                detail=str(exc.reason),
                api_key=api_key,
                attempt=attempt,
            )
            raise RuntimeError(f"Gemini TTS request failed: {exc.reason}") from exc

        except Exception as exc:
            # Other unexpected errors (e.g. JSON decoding, wave structure, etc.) — log and raise
            _log_error_to_disk(
                base_dir=base_dir,
                scene_id=scene_id,
                error_type="UnexpectedError",
                status_code=None,
                message=str(exc),
                detail=None,
                api_key=api_key,
                attempt=attempt,
            )
            raise exc

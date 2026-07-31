from __future__ import annotations

import json
import math
import os
from pathlib import Path
import ssl
import base64
import urllib.error
import urllib.request

from . import ffmpeg
from .models import Manifest


def _load_env_keys() -> None:
    """Load API keys from the namespaced XDG config file and the project-local .env.

    Priority order (first match wins, already-set env vars are never overwritten):
      1. ~/.config/story-video-maker/.env  — project-scoped, outside the repo, never committed.
      2. <project_root>/.env               — optional local override (gitignored).
    """
    project_root = Path(__file__).resolve().parent.parent.parent
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


def create_placeholder_audio(path: Path, duration: float, force: bool = False) -> None:
    if path.exists() and not force:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=220:duration={duration:.3f}:sample_rate=44100",
            "-af",
            "volume=0.08,afade=t=in:st=0:d=0.08,afade=t=out:st={:.3f}:d=0.12".format(max(0.0, duration - 0.12)),
            "-c:a",
            "pcm_s16le",
            str(path),
        ]
    )


def estimate_placeholder_duration(text: str) -> float:
    devanagari_chars = sum(1 for char in text if "\u0900" <= char <= "\u097f")
    return max(5.0, min(12.0, 2.2 + devanagari_chars / 13.5))


def measure_scene_audio(manifest: Manifest, base_dir: Path) -> None:
    for scene in manifest.scenes:
        if not scene.audio_path:
            continue
        duration = ffmpeg.probe_duration(base_dir / scene.audio_path)
        scene.duration_seconds = round(duration, 3)
        if not math.isfinite(duration) or duration <= 0:
            scene.errors.append("Invalid audio duration")


def prepare_narration_audio(manifest: Manifest, base_dir: Path, force: bool = False) -> None:
    provider = manifest.voice.provider
    if provider == "existing_audio":
        validate_existing_audio(manifest, base_dir)
        return
    if provider == "groq_tts":
        generate_groq_audio(manifest, base_dir, force=force)
        return
    if provider == "sarvam_tts":
        generate_sarvam_audio(manifest, base_dir, force=force)
        return
    if provider == "gemini_tts":
        generate_gemini_audio(manifest, base_dir, force=force)
        return
    raise ValueError(f"Unsupported voice provider: {provider}")


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
        paced_rel = f"generated/audio/paced/{scene.id}.wav"
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


def validate_existing_audio(manifest: Manifest, base_dir: Path) -> None:
    for scene in manifest.scenes:
        if not scene.audio_path:
            raise FileNotFoundError(f"{scene.id}: missing audio_path")
        path = base_dir / scene.audio_path
        if not path.exists():
            raise FileNotFoundError(f"{scene.id}: audio not found: {scene.audio_path}")
        ffmpeg.probe_duration(path)


def generate_groq_audio(manifest: Manifest, base_dir: Path, force: bool = False) -> None:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set")

    model = manifest.voice.model or "canopylabs/orpheus-v1-english"
    voice = manifest.voice.voice or "autumn"
    response_format = manifest.voice.response_format or "wav"

    for scene in manifest.scenes:
        if len(scene.narration) > 200 and model.startswith("canopylabs/orpheus"):
            raise ValueError(f"{scene.id}: Groq Orpheus TTS input exceeds 200 characters")
        scene.audio_path = _raw_audio_path(scene.id, response_format)
        out_path = base_dir / scene.audio_path
        if out_path.exists() and not force:
            continue
        out_path.parent.mkdir(parents=True, exist_ok=True)
        _call_groq_tts(
            api_key=api_key,
            model=model,
            voice=voice,
            text=scene.narration,
            response_format=response_format,
            sample_rate=manifest.voice.sample_rate,
            speed=manifest.voice.speed,
            out_path=out_path,
        )
        ffmpeg.probe_duration(out_path)


def generate_groq_preview(
    manifest: Manifest,
    base_dir: Path,
    text: str | None = None,
    out_path: Path | None = None,
    force: bool = False,
) -> Path:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set")
    model = manifest.voice.model or "canopylabs/orpheus-v1-english"
    voice = manifest.voice.voice or "autumn"
    response_format = manifest.voice.response_format or "wav"
    preview_text = text or manifest.scenes[0].narration
    if len(preview_text) > 200 and model.startswith("canopylabs/orpheus"):
        raise ValueError("Groq Orpheus TTS preview input exceeds 200 characters")
    extension = "wav" if response_format == "mulaw" else response_format
    destination = out_path or base_dir / f"generated/audio/previews/{model.split('/')[-1]}-{voice}.{extension}"
    if destination.exists() and not force:
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    _call_groq_tts(
        api_key=api_key,
        model=model,
        voice=voice,
        text=preview_text,
        response_format=response_format,
        sample_rate=manifest.voice.sample_rate,
        speed=manifest.voice.speed,
        out_path=destination,
    )
    ffmpeg.probe_duration(destination)
    return destination


def generate_voice_preview(
    manifest: Manifest,
    base_dir: Path,
    text: str | None = None,
    out_path: Path | None = None,
    force: bool = False,
) -> Path:
    if manifest.voice.provider == "groq_tts":
        return generate_groq_preview(manifest, base_dir, text=text, out_path=out_path, force=force)
    if manifest.voice.provider == "sarvam_tts":
        return generate_sarvam_preview(manifest, base_dir, text=text, out_path=out_path, force=force)
    if manifest.voice.provider == "gemini_tts":
        return generate_gemini_preview(manifest, base_dir, text=text, out_path=out_path, force=force)
    raise ValueError(f"voice-preview is not supported for provider: {manifest.voice.provider}")


def generate_sarvam_audio(manifest: Manifest, base_dir: Path, force: bool = False) -> None:
    api_key = os.environ.get("SARVAM_API_KEY")
    if not api_key:
        raise RuntimeError("SARVAM_API_KEY is not set")

    model = manifest.voice.model or "bulbul:v3"
    speaker = _sarvam_speaker(manifest)
    response_format = manifest.voice.response_format or "wav"
    transport = manifest.voice.transport or "rest_stream"

    for scene in manifest.scenes:
        text_limit = _sarvam_text_limit(model, transport)
        if len(scene.narration) > text_limit:
            raise ValueError(f"{scene.id}: Sarvam TTS input exceeds {text_limit} characters")
        scene.audio_path = _raw_audio_path(scene.id, response_format)
        out_path = base_dir / scene.audio_path
        if out_path.exists() and not force:
            continue
        out_path.parent.mkdir(parents=True, exist_ok=True)
        _call_sarvam_tts(
            api_key=api_key,
            model=model,
            speaker=speaker,
            text=scene.narration,
            target_language_code=manifest.project.language,
            output_audio_codec=response_format,
            sample_rate=manifest.voice.sample_rate,
            pace=manifest.voice.speed,
            transport=transport,
            out_path=out_path,
        )
        ffmpeg.probe_duration(out_path)


def generate_sarvam_preview(
    manifest: Manifest,
    base_dir: Path,
    text: str | None = None,
    out_path: Path | None = None,
    force: bool = False,
) -> Path:
    api_key = os.environ.get("SARVAM_API_KEY")
    if not api_key:
        raise RuntimeError("SARVAM_API_KEY is not set")
    model = manifest.voice.model or "bulbul:v3"
    speaker = _sarvam_speaker(manifest)
    response_format = manifest.voice.response_format or "wav"
    transport = manifest.voice.transport or "rest_stream"
    preview_text = text or "नमस्ते, आज मैं आपकी क्या मदद कर सकता हूँ?"
    text_limit = _sarvam_text_limit(model, transport)
    if len(preview_text) > text_limit:
        raise ValueError(f"Sarvam TTS preview input exceeds {text_limit} characters")
    destination = out_path or base_dir / f"generated/audio/previews/{model.replace(':', '-')}-{speaker}.{response_format}"
    if destination.exists() and not force:
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    _call_sarvam_tts(
        api_key=api_key,
        model=model,
        speaker=speaker,
        text=preview_text,
        target_language_code=manifest.project.language,
        output_audio_codec=response_format,
        sample_rate=manifest.voice.sample_rate,
        pace=manifest.voice.speed,
        transport=transport,
        out_path=destination,
    )
    ffmpeg.probe_duration(destination)
    return destination


def _raw_audio_path(scene_id: str, response_format: str | None = "wav") -> str:
    extension = "wav" if response_format == "mulaw" else (response_format or "wav")
    return f"generated/audio/{scene_id}.{extension}"


def _sarvam_speaker(manifest: Manifest) -> str:
    return manifest.voice.voice or manifest.voice.female_voice or "priya"


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


def _call_groq_tts(
    *,
    api_key: str,
    model: str,
    voice: str,
    text: str,
    response_format: str,
    sample_rate: int | None,
    speed: float | None,
    out_path: Path,
) -> None:
    body = {
        "model": model,
        "voice": voice,
        "input": text,
        "response_format": response_format,
    }
    if sample_rate is not None:
        body["sample_rate"] = sample_rate
    if speed is not None:
        body["speed"] = speed
    request = urllib.request.Request(
        "https://api.groq.com/openai/v1/audio/speech",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "audio/wav,application/octet-stream,*/*",
            "User-Agent": "story-video-maker/0.1",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90, context=_ssl_context()) as response:
            out_path.write_bytes(response.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1200]
        raise RuntimeError(f"Groq TTS request failed with HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Groq TTS request failed: {exc.reason}") from exc


def _call_sarvam_tts(
    *,
    api_key: str,
    model: str,
    speaker: str,
    text: str,
    target_language_code: str,
    output_audio_codec: str,
    sample_rate: int | None,
    pace: float | None,
    transport: str | None,
    out_path: Path,
) -> None:
    if (transport or "rest_stream") == "rest":
        _call_sarvam_tts_rest(
            api_key=api_key,
            model=model,
            speaker=speaker,
            text=text,
            target_language_code=target_language_code,
            output_audio_codec=output_audio_codec,
            sample_rate=sample_rate,
            pace=pace,
            out_path=out_path,
        )
        return
    _call_sarvam_tts_stream(
        api_key=api_key,
        model=model,
        speaker=speaker,
        text=text,
        target_language_code=target_language_code,
        output_audio_codec=output_audio_codec,
        sample_rate=sample_rate,
        pace=pace,
        out_path=out_path,
    )


def _call_sarvam_tts_rest(
    *,
    api_key: str,
    model: str,
    speaker: str,
    text: str,
    target_language_code: str,
    output_audio_codec: str,
    sample_rate: int | None,
    pace: float | None,
    out_path: Path,
) -> None:
    body = {
        "model": model,
        "text": text,
        "target_language_code": target_language_code,
        "speaker": speaker,
        "output_audio_codec": output_audio_codec,
    }
    if sample_rate is not None:
        body["speech_sample_rate"] = sample_rate
    if pace is not None:
        body["pace"] = pace
    request = urllib.request.Request(
        "https://api.sarvam.ai/text-to-speech",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "api-subscription-key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "story-video-maker/0.1",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90, context=_ssl_context()) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1200]
        raise RuntimeError(f"Sarvam TTS request failed with HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Sarvam TTS request failed: {exc.reason}") from exc
    audios = data.get("audios") or []
    if not audios:
        raise RuntimeError("Sarvam TTS response did not contain audio")
    out_path.write_bytes(base64.b64decode(audios[0]))


def _call_sarvam_tts_stream(
    *,
    api_key: str,
    model: str,
    speaker: str,
    text: str,
    target_language_code: str,
    output_audio_codec: str,
    sample_rate: int | None,
    pace: float | None,
    out_path: Path,
) -> None:
    body = {
        "model": model,
        "text": text,
        "target_language_code": target_language_code,
        "speaker": speaker,
        "output_audio_codec": output_audio_codec,
    }
    if sample_rate is not None:
        body["speech_sample_rate"] = sample_rate
    if pace is not None:
        body["pace"] = pace
    request = urllib.request.Request(
        "https://api.sarvam.ai/text-to-speech/stream",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "api-subscription-key": api_key,
            "Content-Type": "application/json",
            "Accept": f"audio/{output_audio_codec},application/octet-stream,*/*",
            "User-Agent": "story-video-maker/0.1",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90, context=_ssl_context()) as response:
            out_path.write_bytes(response.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1200]
        raise RuntimeError(f"Sarvam TTS stream request failed with HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Sarvam TTS stream request failed: {exc.reason}") from exc


def _sarvam_text_limit(model: str, transport: str | None = None) -> int:
    if (transport or "rest_stream") == "rest_stream":
        return 3500
    return 1500 if model == "bulbul:v2" else 2500


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
    response_format = manifest.voice.response_format or "wav"
    preview_text = text or "नमस्ते, आज मैं आपकी क्या मदद कर सकता हूँ?"
    extension = "wav"
    destination = out_path or base_dir / f"generated/audio/previews/{model.replace(':', '-')}-{voice}.{extension}"
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
        import wave
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

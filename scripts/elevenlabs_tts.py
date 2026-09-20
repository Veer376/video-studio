#!/usr/bin/env python3
"""Generate speech with ElevenLabs and save it as an audio file.

The shared API key is loaded from ~/.config/projects/.env by default. Values
already present in the process environment take precedence over the file.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


DEFAULT_ENV_FILE = Path("~/.config/projects/.env").expanduser()
DEFAULT_MODEL = "eleven_multilingual_v2"
DEFAULT_OUTPUT_FORMAT = "mp3_44100_128"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a voiceover audio file with ElevenLabs text-to-speech."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--text", help="Text to synthesize.")
    source.add_argument(
        "--text-file",
        type=Path,
        help="UTF-8 text file containing the text to synthesize.",
    )
    parser.add_argument(
        "--voice-id",
        help="ElevenLabs voice ID. Falls back to ELEVENLABS_VOICE_ID when set.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"ElevenLabs TTS model ID (default: {DEFAULT_MODEL}).",
    )
    parser.add_argument(
        "--output-format",
        default=DEFAULT_OUTPUT_FORMAT,
        help=f"ElevenLabs output format (default: {DEFAULT_OUTPUT_FORMAT}).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Destination audio file.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=DEFAULT_ENV_FILE,
        help=f"Environment file containing ELEVENLABS_API_KEY (default: {DEFAULT_ENV_FILE}).",
    )
    parser.add_argument(
        "--stability",
        type=float,
        help="Optional ElevenLabs voice stability override, 0.0-1.0.",
    )
    parser.add_argument(
        "--similarity-boost",
        type=float,
        help="Optional voice similarity override, 0.0-1.0.",
    )
    parser.add_argument(
        "--style",
        type=float,
        help="Optional style exaggeration override, 0.0-1.0.",
    )
    parser.add_argument(
        "--speed",
        type=float,
        help="Optional speaking-speed multiplier.",
    )
    parser.add_argument(
        "--no-speaker-boost",
        action="store_true",
        help="Disable ElevenLabs speaker boost for this request.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configuration without making an API request.",
    )
    return parser.parse_args()


def load_env_file(path: Path) -> None:
    """Load simple KEY=VALUE entries without overriding existing variables."""
    path = path.expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"Environment file not found: {path}")

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def validate_unit_interval(name: str, value: float | None) -> None:
    if value is not None and not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be between 0.0 and 1.0")


def read_text(args: argparse.Namespace) -> str:
    if args.text is not None:
        text = args.text
    else:
        text = args.text_file.expanduser().read_text(encoding="utf-8")
    text = text.strip()
    if not text:
        raise ValueError("Text to synthesize cannot be empty")
    return text


def build_voice_settings(args: argparse.Namespace) -> dict[str, object] | None:
    validate_unit_interval("stability", args.stability)
    validate_unit_interval("similarity_boost", args.similarity_boost)
    validate_unit_interval("style", args.style)
    if args.speed is not None and args.speed <= 0:
        raise ValueError("speed must be greater than 0")

    settings: dict[str, object] = {}
    if args.stability is not None:
        settings["stability"] = args.stability
    if args.similarity_boost is not None:
        settings["similarity_boost"] = args.similarity_boost
    if args.style is not None:
        settings["style"] = args.style
    if args.speed is not None:
        settings["speed"] = args.speed
    if args.no_speaker_boost:
        settings["use_speaker_boost"] = False
    return settings or None


def main() -> int:
    args = parse_args()
    try:
        load_env_file(args.env_file)
        api_key = os.environ.get("ELEVENLABS_API_KEY")
        if not api_key:
            raise ValueError(
                f"ELEVENLABS_API_KEY is not set in the environment or {args.env_file.expanduser()}"
            )

        voice_id = args.voice_id or os.environ.get("ELEVENLABS_VOICE_ID")
        if not voice_id:
            raise ValueError(
                "A voice is required: pass --voice-id or set ELEVENLABS_VOICE_ID"
            )

        text = read_text(args)
        voice_settings = build_voice_settings(args)

        if args.dry_run:
            print(f"env_file={args.env_file.expanduser()}")
            print("api_key=present")
            print(f"voice_id={voice_id}")
            print(f"model={args.model}")
            print(f"output_format={args.output_format}")
            print(f"text_chars={len(text)}")
            print(f"output={args.output.expanduser()}")
            return 0

        payload: dict[str, object] = {
            "text": text,
            "model_id": args.model,
        }
        if voice_settings is not None:
            payload["voice_settings"] = voice_settings

        query = urllib.parse.urlencode({"output_format": args.output_format})
        url = (
            "https://api.elevenlabs.io/v1/text-to-speech/"
            f"{urllib.parse.quote(voice_id, safe='')}?{query}"
        )
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
                "xi-api-key": api_key,
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                audio = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"ElevenLabs request failed with HTTP {exc.code}: {detail}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"ElevenLabs request failed: {exc.reason}") from exc

        output = args.output.expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(audio)
        print(f"Wrote {output} ({len(audio)} bytes)")
        return 0
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

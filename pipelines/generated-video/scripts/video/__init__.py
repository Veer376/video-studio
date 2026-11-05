"""Unified video generation package supporting Google Gemini and Google Flow backends."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Sequence

from .base import (
    HANDLE_PATTERN,
    PROJECT_ROOT,
    BaseProvider,
    CharacterEntry,
    LocationEntry,
    CompiledScene,
    ConfigError,
    CreditError,
    ProviderUnavailableError,
    VideoError,
    compile_scene,
    format_character_brief,
    format_location_brief,
    load_characters,
    load_locations,
    load_json,
    resolve_characters_path,
    resolve_locations_path,
    resolve_path,
)
from .flow import FlowProvider
from .google import GoogleProvider


PROVIDERS: dict[str, type[BaseProvider]] = {
    "google": GoogleProvider,
    "flow": FlowProvider,
}


def get_provider(name: str = "google", **kwargs: Any) -> BaseProvider:
    """Instantiate and return a video provider by name ('google' or 'flow')."""
    key = name.strip().lower()
    provider_cls = PROVIDERS.get(key)
    if not provider_cls:
        raise ValueError(f"Unknown video provider {name!r}. Supported providers: {list(PROVIDERS.keys())}")
    return provider_cls(**kwargs)  # type: ignore


def generate_video(
    *,
    prompt: str,
    output: Path,
    provider: str = "google",
    images: Sequence[Path] = (),
    videos: Sequence[Path] = (),
    task: str | None = None,
    aspect_ratio: str = "16:9",
    duration: int = 10,
    model: str | None = None,
    provider_instance: BaseProvider | None = None,
    **kwargs: Any,
) -> int:
    """Generate one video using the selected provider and save it to output path."""
    active_provider = provider_instance or get_provider(provider, **kwargs)
    return active_provider.generate_video(
        prompt=prompt,
        output=output,
        images=images,
        videos=videos,
        task=task,
        aspect_ratio=aspect_ratio,
        duration=duration,
        model=model,
        **kwargs,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Unified video generator using Google Gemini Omni Flash or Google Flow."
    )
    parser.add_argument(
        "--provider",
        choices=("google", "flow"),
        default="google",
        help="Generation provider (default: google)",
    )
    parser.add_argument("--prompt", "-p", required=True, help="Video prompt text")
    parser.add_argument("--output", "-o", type=Path, required=True, help="Destination .mp4 path")
    parser.add_argument(
        "--image",
        "--ref-file",
        type=Path,
        action="append",
        default=[],
        dest="images",
        help="Reference image path (can be repeated)",
    )
    parser.add_argument("--start", type=Path, default=None, help="Start frame image path")
    parser.add_argument("--end", type=Path, default=None, help="End frame image path")
    parser.add_argument("--duration", "-d", type=int, choices=[4, 6, 8, 10], default=10)
    parser.add_argument("--aspect-ratio", "--aspect", choices=["16:9", "9:16", "landscape", "portrait"], default="16:9")
    parser.add_argument("--model", default=None, help="Model override")
    parser.add_argument("--backend", choices=("auto", "vertex", "developer"), default="auto", help="Google backend")
    parser.add_argument("--gcp-project", default=None, help="Google Cloud project override")
    parser.add_argument("--flow-host", default="127.0.0.1:8001", help="Flow agent server host:port")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    aspect = "9:16" if args.aspect_ratio in {"9:16", "portrait"} else "16:9"

    if args.provider == "google":
        provider_instance = GoogleProvider(backend=args.backend, gcp_project=args.gcp_project)
    else:
        provider_instance = FlowProvider(host=args.flow_host)

    print(f"Using provider: {args.provider}")
    byte_count = generate_video(
        prompt=args.prompt,
        output=args.output,
        provider_instance=provider_instance,
        images=args.images,
        aspect_ratio=aspect,
        duration=args.duration,
        model=args.model,
        start_frame=args.start,
        end_frame=args.end,
    )
    print(f"Saved {byte_count:,} bytes to {args.output}")


__all__ = [
    "BaseProvider",
    "CharacterEntry",
    "LocationEntry",
    "CompiledScene",
    "ConfigError",
    "CreditError",
    "FlowProvider",
    "GoogleProvider",
    "HANDLE_PATTERN",
    "PROJECT_ROOT",
    "ProviderUnavailableError",
    "VideoError",
    "compile_scene",
    "format_character_brief",
    "format_location_brief",
    "generate_video",
    "get_provider",
    "load_characters",
    "load_locations",
    "load_json",
    "resolve_characters_path",
    "resolve_locations_path",
    "resolve_path",
]


if __name__ == "__main__":
    main()

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from studio.core.io import read_json
from studio.core.paths import project_root


SUPPORTED_IMAGE_PROVIDERS = {"cloudflare", "flow", "google"}


@dataclass(frozen=True)
class ProductionConfig:
    image_provider: str
    image_model: str
    subtitles: bool
    zoom: bool
    closing_fade: bool = True


def _strict_bool(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"production.{field} must be true or false")
    return value


def is_short_project(session: dict | None) -> bool:
    data = session or {}
    aspect_ratio = data.get("visual", {}).get("aspect_ratio")
    duration = data.get("brief", {}).get("target_duration_seconds")
    return aspect_ratio == "9:16" and (
        duration is None
        or isinstance(duration, (int, float)) and not isinstance(duration, bool) and duration <= 180
    )


def load_production_config(
    session: dict | None = None,
    *,
    provider: str | None = None,
    model: str | None = None,
    subtitles: bool | None = None,
    zoom: bool | None = None,
    closing_fade: bool | None = None,
    config_path: Path | None = None,
) -> ProductionConfig:
    """Resolve production settings: invocation overrides > repository config."""
    path = config_path or project_root() / "kathamind" / "config.json"
    root = read_json(path) if path.exists() else {}
    configured = root.get("production", {})
    if not isinstance(configured, dict):
        raise ValueError(f"{path} production must be an object")

    configured_short = configured.get("short", {})
    if not isinstance(configured_short, dict):
        raise ValueError(f"{path} production.short must be an object")

    values = {key: value for key, value in configured.items() if key != "short"}
    if is_short_project(session):
        values.update(configured_short)
    configured_provider = str(values.get("image_provider") or "").strip().lower()
    image_provider = str(provider or configured_provider).strip().lower()
    image_model = str(model or values.get("image_model") or "").strip()
    if provider and provider != configured_provider and model is None:
        raise ValueError("changing image provider requires an explicit image model")
    if image_provider not in SUPPORTED_IMAGE_PROVIDERS:
        choices = ", ".join(sorted(SUPPORTED_IMAGE_PROVIDERS))
        raise ValueError(f"production.image_provider must be one of: {choices}")
    if not image_model:
        raise ValueError("production.image_model must be a non-empty string")

    return ProductionConfig(
        image_provider=image_provider,
        image_model=image_model,
        subtitles=(
            _strict_bool(subtitles, "subtitles")
            if subtitles is not None
            else _strict_bool(values.get("subtitles", True), "subtitles")
        ),
        zoom=(
            _strict_bool(zoom, "zoom")
            if zoom is not None
            else _strict_bool(values.get("zoom", True), "zoom")
        ),
        closing_fade=(
            _strict_bool(closing_fade, "closing_fade")
            if closing_fade is not None
            else _strict_bool(values.get("closing_fade", True), "closing_fade")
        ),
    )

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import SUPPORTED_THUMBNAIL_SUFFIXES, THUMBNAIL_MAX_BYTES, die


def load_pillow():
    try:
        from PIL import Image
    except ModuleNotFoundError:
        die("missing Pillow. Install with: python3 -m pip install --user pillow")
    return Image


def compressed_thumbnail_path(source: Path, quality: int, scale_percent: int) -> Path:
    stem = f"{source.stem}-youtube-q{quality}"
    if scale_percent != 100:
        stem += f"-s{scale_percent}"
    return source.with_name(f"{stem}.jpg")


def compress_thumbnail(
    source: Path,
    *,
    quality: int,
    scale_percent: int,
    max_bytes: int = THUMBNAIL_MAX_BYTES,
    output: Path | None = None,
) -> tuple[Path, dict[str, Any]]:
    if source.suffix.lower() not in SUPPORTED_THUMBNAIL_SUFFIXES:
        die(f"unsupported thumbnail extension: {source}")
    if not 1 <= quality <= 100:
        die("--quality must be between 1 and 100")
    if not 10 <= scale_percent <= 100:
        die("--scale-percent must be between 10 and 100")

    Image = load_pillow()
    out = output or compressed_thumbnail_path(source, quality, scale_percent)
    image = Image.open(source).convert("RGB")
    original_size = image.size
    if scale_percent != 100:
        resized = (
            max(1, int(original_size[0] * scale_percent / 100)),
            max(1, int(original_size[1] * scale_percent / 100)),
        )
        image = image.resize(resized, Image.Resampling.LANCZOS)

    attempts: list[dict[str, Any]] = []
    current_quality = quality
    while current_quality >= 40:
        image.save(out, "JPEG", quality=current_quality, optimize=True, progressive=True)
        size = out.stat().st_size
        attempts.append({"quality": current_quality, "size_bytes": size})
        if size <= max_bytes:
            return out, {
                "source": str(source),
                "output": str(out),
                "original_size": original_size,
                "final_size": image.size,
                "quality": current_quality,
                "scale_percent": scale_percent,
                "size_bytes": size,
                "max_bytes": max_bytes,
                "attempts": attempts,
            }
        current_quality -= 5

    return out, {
        "source": str(source),
        "output": str(out),
        "original_size": original_size,
        "final_size": image.size,
        "quality": current_quality + 5,
        "scale_percent": scale_percent,
        "size_bytes": out.stat().st_size if out.exists() else None,
        "max_bytes": max_bytes,
        "attempts": attempts,
        "warning": "compressed thumbnail is still over the max byte limit",
    }


def ensure_uploadable_thumbnail(
    source: Path | None,
    *,
    quality: int,
    scale_percent: int,
    max_bytes: int = THUMBNAIL_MAX_BYTES,
) -> tuple[Path | None, str | None, dict[str, Any] | None]:
    if source is None:
        return None, None, None
    if not source.exists() or not source.is_file():
        die(f"thumbnail file does not exist: {source}")
    if source.suffix.lower() not in SUPPORTED_THUMBNAIL_SUFFIXES:
        die(f"unsupported thumbnail extension: {source}")
    if source.stat().st_size <= max_bytes:
        return source, None, None

    compressed, info = compress_thumbnail(
        source,
        quality=quality,
        scale_percent=scale_percent,
        max_bytes=max_bytes,
    )
    if compressed.stat().st_size <= max_bytes:
        return compressed, f"compressed oversized thumbnail: {source}", info
    return None, f"thumbnail remains over max size after compression: {compressed}", info

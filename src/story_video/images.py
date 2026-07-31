from __future__ import annotations

from pathlib import Path

from . import ffmpeg


def create_placeholder_image(path: Path, text: str, size: tuple[int, int] = (1920, 1080), force: bool = False) -> None:
    if path.exists() and not force:
        return
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise RuntimeError("Pillow is required to create placeholder images") from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    width, height = size
    image = Image.new("RGB", size, "#30251c")
    draw = ImageDraw.Draw(image)
    for y in range(height):
        blend = y / max(1, height - 1)
        r = int(48 + 55 * blend)
        g = int(37 + 45 * blend)
        b = int(28 + 30 * blend)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    margin = max(24, min(width, height) // 12)
    draw.rectangle([margin, margin, width - margin, height - margin], outline="#c58d38", width=max(4, margin // 8))
    font = ImageFont.load_default(size=max(18, min(width, height) // 12))
    bbox = draw.textbbox((0, 0), text, font=font)
    draw.text(((width - (bbox[2] - bbox[0])) / 2, (height - (bbox[3] - bbox[1])) / 2), text, fill="#f3d9a2", font=font)
    image.save(path)


def validate_image(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")
    ffmpeg.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "json", str(path)])

from __future__ import annotations

from pathlib import Path

from .models import Manifest


def write_srt(manifest: Manifest, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cursor = 0.0
    entries: list[str] = []
    for index, scene in enumerate(manifest.scenes, start=1):
        duration = float(scene.duration_seconds or 0)
        start = cursor
        end = cursor + duration
        lines = break_subtitle(scene.subtitle or scene.narration)
        entries.append(f"{index}\n{format_srt_time(start)} --> {format_srt_time(end)}\n{lines}\n")
        cursor = end
    out_path.write_text("\n".join(entries), encoding="utf-8")
    return out_path


def write_subtitle_overlay(
    text: str,
    out_path: Path,
    size: tuple[int, int],
    font_path: Path | None,
    h_margin_pct: float = 0.10,
) -> Path:
    """Render subtitle text as a transparent RGBA PNG overlay.

    Args:
        text:          Narration text to display.
        out_path:      Destination PNG path.
        size:          Canvas size (width, height) in pixels.
        font_path:     Path to a Devanagari-compatible .ttf/.ttc font.
        h_margin_pct:  Fraction of width reserved as left+right margin (default 10% each side).
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise RuntimeError("Pillow is required to render subtitle overlays when FFmpeg lacks libass") from exc

    width, height = size
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    font_size = max(24, round(height * 0.047))
    font = ImageFont.truetype(str(font_path), font_size) if font_path else ImageFont.load_default(size=font_size)

    # Maximum pixel width a line of text may occupy (canvas minus horizontal margins)
    max_line_px = width - 2 * round(width * h_margin_pct)

    # Pixel-width-aware word wrapping — never measure by character count
    lines = _wrap_text_px(draw, text, font, max_line_px)

    line_gap = round(font_size * 0.35)
    metrics = [draw.textbbox((0, 0), line, font=font) for line in lines]
    total_height = sum(box[3] - box[1] for box in metrics) + line_gap * max(0, len(lines) - 1)
    y = height - total_height - round(height * 0.07)
    pad_x = round(font_size * 0.45)
    pad_y = round(font_size * 0.28)

    for line, box in zip(lines, metrics):
        text_width = box[2] - box[0]
        text_height = box[3] - box[1]
        x = (width - text_width) / 2
        draw.rounded_rectangle(
            [x - pad_x, y - pad_y, x + text_width + pad_x, y + text_height + pad_y],
            radius=10,
            fill=(0, 0, 0, 130),
        )
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255), stroke_width=1, stroke_fill=(0, 0, 0, 180))
        y += text_height + line_gap

    image.save(out_path)
    return out_path


def _wrap_text_px(draw: "ImageDraw.ImageDraw", text: str, font: "ImageFont.FreeTypeFont", max_px: int) -> list[str]:
    """Wrap `text` into lines that each fit within `max_px` pixels when rendered with `font`."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        w = draw.textbbox((0, 0), candidate, font=font)[2]
        if w > max_px and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    # Cap at 2 properly-fitted lines — word-by-word subtitle mode handles long text
    return lines[:2]


def break_subtitle(text: str, max_chars: int = 42) -> str:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) > max_chars and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return "\n".join(lines[:2] if len(lines) <= 2 else [" ".join(lines[:-1]), lines[-1]])


def format_srt_time(seconds: float) -> str:
    millis = round(seconds * 1000)
    hours, remainder = divmod(millis, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"

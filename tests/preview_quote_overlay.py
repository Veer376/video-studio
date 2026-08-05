#!/usr/bin/env python3
"""
Quote Overlay Preview Generator for Story Video Maker studio.

Features:
- Warm ivory text (#F6EECF) with saffron-gold quotation marks & accents.
- Top and bottom gold diamond hairline flourishes.
- Smooth Hermite radial background vignette (50% stretched travel distance, center_alpha=185).
- Per-word/per-line soft blackish gradient halo blur (20% increased intensity, alpha=144, 15% expanded spread).

Usage:
    python3 tests/preview_quote_overlay.py --input library/2026-08-02_osho-pyaas-ki-keemat/images/scene-001.png --output output/preview_quote.png
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

try:
    from renderer import detect_devanagari_font
except ImportError:
    def detect_devanagari_font(root: Path) -> Path | None:
        font_paths = [
            Path("/System/Library/Fonts/Supplemental/DevanagariSangamMN.ttc"),
            Path("/System/Library/Fonts/Supplemental/NotoSansDevanagari.ttf"),
            Path("/System/Library/Fonts/KohinoorDevanagari.ttc"),
        ]
        for p in font_paths:
            if p.exists():
                return p
        return None


# ── Color Palette ─────────────────────────────────────────────────────────────
PALETTE = {
    "text": (246, 238, 207, 255),       # #F6EECF warm ivory
    "accent": (221, 169, 72, 255),      # #DDA948 muted saffron-gold
    "line": (201, 150, 62, 185),        # #C9963E hairline divider
    "halo": (0, 0, 0, 145),             # Per-word soft blackish gradient halo
    "stroke": (20, 15, 10, 160),        # Subtle dark text outline edge
    "shadow": (18, 14, 9, 200),         # Text drop shadow
    "glow": (221, 169, 72, 42),         # Subtle gold glow
}


def load_font(path: Path | str | None, size: int) -> ImageFont.FreeTypeFont:
    """Load font using RAQM layout engine when available for Hindi ligatures."""
    if not path or not Path(path).exists():
        return ImageFont.load_default()
    try:
        return ImageFont.truetype(
            str(path),
            size=size,
            layout_engine=ImageFont.Layout.RAQM,
        )
    except (AttributeError, OSError):
        try:
            return ImageFont.truetype(str(path), size=size)
        except Exception:
            return ImageFont.load_default()


def create_smooth_radial_vignette(
    width: int,
    height: int,
    center_alpha: int = 185,
    edge_alpha: int = 0,
) -> Image.Image:
    """
    Creates a continuous Hermite radial gradient background vignette.
    Stretches 50% further across the canvas for ultra-smooth transition from Center to Edge.
    """
    gw, gh = 300, 300
    low = Image.new("L", (gw, gh), 0)
    pix = low.load()
    cx, cy = gw / 2.0, gh / 2.0
    max_r = math.sqrt(cx * cx + cy * cy)

    for y in range(gh):
        for x in range(gw):
            # Scale distance by 0.55 to stretch vignette travel distance 50% further towards edges
            dist = (math.sqrt((x - cx) ** 2 + (y - cy) ** 2) / max_r) * 0.55
            d = max(0.0, min(1.0, dist))
            # Smoothstep (Hermite interpolation): 1 - (3d^2 - 2d^3)
            smooth_val = 1.0 - (3.0 * (d ** 2) - 2.0 * (d ** 3))
            pix[x, y] = int(edge_alpha + (center_alpha - edge_alpha) * smooth_val)

    grad_mask = low.resize((width, height), Image.Resampling.BICUBIC)
    dark = Image.new("RGBA", (width, height), (0, 0, 0, 255))
    dark.putalpha(grad_mask)
    return dark


def draw_flourish(
    draw: ImageDraw.ImageDraw,
    cx: int,
    y: int,
    half_width: int,
) -> None:
    """Draw thin hairline + small central diamond & dot accents."""
    c = PALETTE["line"]
    gap = max(14, half_width // 12)

    draw.line((cx - half_width, y, cx - gap, y), fill=c, width=1)
    draw.line((cx + gap, y, cx + half_width, y), fill=c, width=1)

    diamond = max(4, half_width // 35)
    draw.polygon(
        [
            (cx, y - diamond),
            (cx + diamond, y),
            (cx, y + diamond),
            (cx - diamond, y),
        ],
        fill=PALETTE["accent"],
    )

    dot_r = max(2, diamond // 2)
    for dx in (-gap - 7, gap + 7):
        draw.ellipse(
            (cx + dx - dot_r, y - dot_r, cx + dx + dot_r, y + dot_r),
            fill=c,
        )


def draw_centered_lines(
    layer: Image.Image,
    lines: Iterable[str],
    font: ImageFont.FreeTypeFont,
    center: tuple[int, int],
    line_step: int,
    fill: tuple[int, int, int, int],
    stroke_width: int = 0,
    stroke_fill: tuple[int, int, int, int] | None = None,
    offset: tuple[int, int] = (0, 0),
) -> list[tuple[float, float, float]]:
    """Draw centered lines of text."""
    draw = ImageDraw.Draw(layer)
    lines = list(lines)
    cx, cy = center
    cx += offset[0]
    cy += offset[1]

    first_y = cy - ((len(lines) - 1) * line_step) / 2
    metrics: list[tuple[float, float, float]] = []

    for index, line in enumerate(lines):
        y = first_y + index * line_step
        box = draw.textbbox((0, 0), line, font=font)
        width = box[2] - box[0]
        draw.text(
            (cx, y),
            line,
            font=font,
            fill=fill,
            anchor="mm",
            align="center",
            stroke_width=stroke_width,
            stroke_fill=stroke_fill,
        )
        metrics.append((y, width, cx))

    return metrics


def render_quote(
    background: Image.Image,
    text: str,
    font_path: Path | str | None,
    transparent: bool = False,
    center_vignette_alpha: int = 0,
) -> Image.Image:
    """Render full quote overlay onto background image."""
    background = background.convert("RGBA")
    w, h = background.size

    cx = int(w * 0.500)
    cy = int(h * 0.500)

    font_size = max(38, int(w * 0.045))
    quote_size = int(font_size * 1.30)
    line_step = int(font_size * 1.50)

    font = load_font(font_path, font_size)
    quote_font = load_font(font_path, quote_size)

    lines = [line.strip() for line in text.split("\n") if line.strip()]

    if transparent:
        result = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    else:
        # 1. Background Image Vignette: Smooth radial vignette (center_alpha=185, edge_alpha=0)
        vignette_overlay = create_smooth_radial_vignette(w, h, center_alpha=center_vignette_alpha, edge_alpha=0)
        result = Image.alpha_composite(background, vignette_overlay)

    # 2. Per-Word Soft Blackish Gradient Halo Layer
    text_halo = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw_centered_lines(
        text_halo,
        lines,
        font,
        (cx, cy),
        line_step,
        fill=PALETTE["halo"],
        stroke_width=max(8, int(font_size * 0.20)),
        stroke_fill=PALETTE["halo"],
    )
    blur_radius = max(10, int(font_size * 0.26))
    blurred_halo = text_halo.filter(ImageFilter.GaussianBlur(blur_radius))
    result = Image.alpha_composite(result, blurred_halo)

    # 3. Main Ivory Text Layer
    text_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    line_metrics = draw_centered_lines(
        text_layer,
        lines,
        font,
        (cx, cy),
        line_step,
        PALETTE["text"],
        stroke_width=max(1, int(font_size * 0.025)),
        stroke_fill=PALETTE["stroke"],
    )

    # 4. Gold Quotation Marks (“ and ”)
    td = ImageDraw.Draw(text_layer)
    first_y, first_width, _ = line_metrics[0]
    last_y, last_width, _ = line_metrics[-1]

    td.text(
        (cx - first_width / 2 - quote_size * 0.40, first_y - quote_size * 0.08),
        "“",
        font=quote_font,
        fill=PALETTE["accent"],
        anchor="mm",
    )
    td.text(
        (cx + last_width / 2 + quote_size * 0.30, last_y + quote_size * 0.08),
        "”",
        font=quote_font,
        fill=PALETTE["accent"],
        anchor="mm",
    )

    # 5. Top & Bottom Gold Diamond Hairline Flourishes
    flourish_half_width = int(w * 0.12)
    top_y = int(first_y - font_size * 1.10)
    bottom_y = int(last_y + font_size * 1.10)
    draw_flourish(td, cx, top_y, flourish_half_width)
    draw_flourish(td, cx, bottom_y, flourish_half_width)

    result = Image.alpha_composite(result, text_layer)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Render elegant Hindi quote overlay")
    parser.add_argument("--input", default="library/2026-08-02_osho-pyaas-ki-keemat/images/scene-001.png", help="Input image path")
    parser.add_argument("--output", default="output/preview_quote.png", help="Output PNG path")
    parser.add_argument("--font", default=None, help="Font file path")
    parser.add_argument("--text", default="ओशो कहते हैं—\nतीव्र प्यास राह बना देती है।\nजब खोज सच्ची हो, तो दिशा पूछनी नहीं पड़ती—\nप्यास ही पथ रच देती है।", help="Quote text")
    parser.add_argument("--transparent", action="store_true", help="Render on transparency")
    args = parser.parse_args()

    input_path = PROJECT_ROOT / args.input if not Path(args.input).is_absolute() else Path(args.input)
    output_path = PROJECT_ROOT / args.output if not Path(args.output).is_absolute() else Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    font_path = Path(args.font) if args.font else detect_devanagari_font(PROJECT_ROOT)
    source = Image.open(input_path)
    result = render_quote(source, args.text, font_path, transparent=args.transparent)
    result.save(output_path)
    print(f"✓ Rendered quote overlay saved to: [preview_quote.png](file://{output_path.resolve()})")


if __name__ == "__main__":
    main()

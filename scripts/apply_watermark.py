#!/usr/bin/env python3
"""
scripts/apply_watermark.py

Overlays a stylized circular channel badge over the bottom-right AI watermark
on vertical Shorts (and standard videos) using Pillow and FFmpeg.

Usage:
  python3 scripts/apply_watermark.py --input <video.mp4> --output <clean_video.mp4> --image <logo.png> [--size 80]
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageOps


def make_circular_badge(
    image_path: Path,
    diameter: int = 80,
    border_width: int = 3,
    border_color: tuple[int, int, int, int] = (255, 255, 255, 220),
    shadow_offset: tuple[int, int] = (2, 4),
    shadow_blur: int = 4,
    shadow_color: tuple[int, int, int, int] = (0, 0, 0, 140),
) -> Image.Image:
    scale = 4
    high_res_dia = diameter * scale
    high_border = border_width * scale

    src = Image.open(image_path).convert("RGBA")
    fitted = ImageOps.fit(src, (high_res_dia, high_res_dia), method=Image.Resampling.LANCZOS)

    mask = Image.new("L", (high_res_dia, high_res_dia), 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.ellipse((0, 0, high_res_dia - 1, high_res_dia - 1), fill=255)

    circle_img = Image.new("RGBA", (high_res_dia, high_res_dia), (0, 0, 0, 0))
    circle_img.paste(fitted, (0, 0), mask)

    if high_border > 0:
        border_img = Image.new("RGBA", (high_res_dia, high_res_dia), (0, 0, 0, 0))
        draw_border = ImageDraw.Draw(border_img)
        draw_border.ellipse(
            (
                high_border // 2,
                high_border // 2,
                high_res_dia - 1 - high_border // 2,
                high_res_dia - 1 - high_border // 2,
            ),
            outline=border_color,
            width=high_border,
        )
        circle_img = Image.alpha_composite(circle_img, border_img)

    badge = circle_img.resize((diameter, diameter), resample=Image.Resampling.LANCZOS)

    pad = (shadow_blur * 2) + max(abs(shadow_offset[0]), abs(shadow_offset[1])) + 4
    canvas_w = diameter + pad * 2
    canvas_h = diameter + pad * 2

    canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

    shadow_mask = Image.new("L", (diameter, diameter), 0)
    ImageDraw.Draw(shadow_mask).ellipse((0, 0, diameter - 1, diameter - 1), fill=shadow_color[3])
    
    shadow_layer = Image.new("RGBA", (diameter, diameter), shadow_color[:3] + (0,))
    shadow_layer.putalpha(shadow_mask)

    shadow_full = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    shadow_x = pad + shadow_offset[0]
    shadow_y = pad + shadow_offset[1]
    shadow_full.paste(shadow_layer, (shadow_x, shadow_y))
    shadow_blurred = shadow_full.filter(ImageFilter.GaussianBlur(radius=shadow_blur))

    canvas = Image.alpha_composite(canvas, shadow_blurred)
    canvas.paste(badge, (pad, pad), badge)

    canvas.info["badge_offset"] = (pad, pad)
    return canvas


def get_video_dimensions(video_path: Path) -> tuple[int, int]:
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=s=x:p=0",
        str(video_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    parts = res.stdout.strip().split("x")
    return int(parts[0]), int(parts[1])


def calculate_watermark_coords(
    width: int,
    height: int,
    badge_diameter: int,
    custom_x: int | None = None,
    custom_y: int | None = None,
) -> tuple[int, int]:
    if custom_x is not None and custom_y is not None:
        return custom_x, custom_y

    center_x = int(width * (605.0 / 720.0))
    center_y = int(height * (1165.0 / 1280.0))

    top_left_x = center_x - (badge_diameter // 2)
    top_left_y = center_y - (badge_diameter // 2)
    return top_left_x, top_left_y


def apply_watermark(
    input_video: Path,
    output_video: Path,
    image_path: Path,
    badge_size: int = 80,
    x: int | None = None,
    y: int | None = None,
    border_width: int = 3,
) -> None:
    if not input_video.exists():
        raise FileNotFoundError(f"Input video not found: {input_video}")
    if not image_path.exists():
        raise FileNotFoundError(f"Watermark image not found: {image_path}")

    output_video.parent.mkdir(parents=True, exist_ok=True)

    w, h = get_video_dimensions(input_video)
    top_left_x, top_left_y = calculate_watermark_coords(w, h, badge_size, x, y)

    badge_canvas = make_circular_badge(
        image_path=image_path,
        diameter=badge_size,
        border_width=border_width,
    )

    pad_x, pad_y = badge_canvas.info.get("badge_offset", (0, 0))
    overlay_x = top_left_x - pad_x
    overlay_y = top_left_y - pad_y

    with tempfile.TemporaryDirectory() as tmpdir:
        temp_badge_path = Path(tmpdir) / "badge_overlay.png"
        badge_canvas.save(temp_badge_path, format="PNG")

        ffmpeg_cmd = [
            "ffmpeg",
            "-y",
            "-i", str(input_video),
            "-i", str(temp_badge_path),
            "-filter_complex", f"[0:v][1:v]overlay={overlay_x}:{overlay_y}:format=auto",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "medium",
            "-crf", "18",
            "-movflags", "+faststart",
            "-c:a", "copy",
            str(output_video),
        ]

        res = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"FFmpeg failed with code {res.returncode}:\n{res.stderr}")

    print(f"✓ Watermark successfully masked: {output_video}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Mask AI watermark with a circular channel badge.")
    parser.add_argument("--input", "-i", type=Path, required=True, help="Path to input MP4 video")
    parser.add_argument("--output", "-o", type=Path, required=True, help="Path to output MP4 video")
    parser.add_argument("--image", "-img", type=Path, required=True, help="Path to logo/avatar image")
    parser.add_argument("--badge-size", "--size", type=int, default=80, help="Diameter of the circular badge in px (default: 80)")
    parser.add_argument("--x", type=int, default=None, help="Custom top-left X coordinate")
    parser.add_argument("--y", type=int, default=None, help="Custom top-left Y coordinate")
    parser.add_argument("--border-width", type=int, default=3, help="Circular border width in px (default: 3)")

    args = parser.parse_args()
    try:
        apply_watermark(
            input_video=args.input,
            output_video=args.output,
            image_path=args.image,
            badge_size=args.badge_size,
            x=args.x,
            y=args.y,
            border_width=args.border_width,
        )
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

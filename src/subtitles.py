from __future__ import annotations

from pathlib import Path

from models import Manifest


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


def subtitle_enable_expr(t_start: float, t_end: float) -> str:
    """Build a non-overlapping FFmpeg enable expression for subtitle overlays."""
    return f"gte(t,{t_start:.4f})*lt(t,{t_end:.4f})"


QUOTE_PALETTE = {
    "text": (246, 238, 207, 255),       # #F6EECF warm ivory
    "accent": (221, 169, 72, 255),      # #DDA948 muted saffron-gold
    "line": (201, 150, 62, 185),        # #C9963E hairline
    "halo": (0, 0, 0, 145),             # Dedicated quote halo (alpha 145)
    "stroke": (20, 15, 10, 160),        # Subtle dark text outline edge
}

SUBTITLE_PALETTE = {
    "text": (246, 238, 207, 255),       # #F6EECF warm ivory
    "halo": (0, 0, 0, 160),             # Dedicated setup subtitle halo (alpha 160)
    "stroke": (20, 15, 10, 160),        # Subtle dark text outline edge
}


def draw_quote_flourish(draw: "ImageDraw.ImageDraw", cx: int, y: int, half_width: int) -> None:
    """Draw thin hairline + small central diamond & dot accents."""
    c = QUOTE_PALETTE["line"]
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
        fill=QUOTE_PALETTE["accent"],
    )

    dot_r = max(2, diamond // 2)
    for dx in (-gap - 7, gap + 7):
        draw.ellipse(
            (cx + dx - dot_r, y - dot_r, cx + dx + dot_r, y + dot_r),
            fill=c,
        )


def write_subtitle_overlay(
    text: str,
    out_path: Path,
    size: tuple[int, int],
    font_path: Path | None,
    h_margin_pct: float = 0.10,
    full_text: str | None = None,
    is_quote: bool = False,
    style: str = "soft_halo",
) -> Path:
    """Render subtitle or quote text as a transparent RGBA PNG overlay."""
    if is_quote:
        return render_quote_overlay(
            text=text,
            out_path=out_path,
            size=size,
            font_path=font_path,
            h_margin_pct=h_margin_pct,
            full_text=full_text,
        )
    return render_subtitle_overlay(
        text=text,
        out_path=out_path,
        size=size,
        font_path=font_path,
        h_margin_pct=h_margin_pct,
        full_text=full_text,
        style=style,
    )


def render_quote_overlay(
    text: str,
    out_path: Path,
    size: tuple[int, int],
    font_path: Path | None,
    h_margin_pct: float = 0.10,
    full_text: str | None = None,
) -> Path:
    """Dedicated module for rendering centered quote overlays."""
    try:
        from PIL import Image, ImageDraw, ImageFont, ImageFilter
    except ImportError as exc:
        raise RuntimeError("Pillow is required to render quote overlays") from exc

    width, height = size
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    font_size = max(24, round(height * 0.048))
    quote_size = round(font_size * 1.30)

    try:
        if font_path:
            try:
                font = ImageFont.truetype(str(font_path), font_size, layout_engine=ImageFont.Layout.RAQM)
                quote_font = ImageFont.truetype(str(font_path), quote_size, layout_engine=ImageFont.Layout.RAQM)
            except Exception:
                font = ImageFont.truetype(str(font_path), font_size)
                quote_font = ImageFont.truetype(str(font_path), quote_size)
        else:
            font = ImageFont.load_default()
            quote_font = font
    except Exception:
        font = ImageFont.load_default()
        quote_font = font

    try:
        ascent, descent = font.getmetrics()
        line_height = ascent + descent
    except AttributeError:
        line_height = font_size

    max_line_px = width - 2 * round(width * h_margin_pct)
    wrap_target = full_text if full_text is not None else text
    if ">" in wrap_target:
        wrap_target = wrap_target.split(">", 1)[1].strip()
    if ">" in text:
        text = text.split(">", 1)[1].strip()

    full_lines = _wrap_text_px(draw, wrap_target, font, max_line_px, max_lines=5)
    total_lines = len(full_lines)
    line_gap = round(font_size * 0.45)
    total_height = total_lines * line_height + line_gap * max(0, total_lines - 1)
    y_start = (height - total_height) / 2
    line_positions = [y_start + i * (line_height + line_gap) for i in range(total_lines)]

    if full_text is not None:
        full_line_word_counts = [len(line.split()) for line in full_lines]
        visible_words = text.split()
        visible_lines = []
        word_idx = 0
        for count in full_line_word_counts:
            line_words = visible_words[word_idx : word_idx + count]
            visible_lines.append(" ".join(line_words))
            word_idx += count
    else:
        visible_lines = _wrap_text_px(draw, text, font, max_line_px, max_lines=5)

    # 1. Dedicated Quote Soft Blackish Gradient Halo Layer (alpha=145, 0.20 stroke mult)
    text_halo = Image.new("RGBA", size, (0, 0, 0, 0))
    halo_draw = ImageDraw.Draw(text_halo)
    for i, line_text in enumerate(visible_lines):
        if not line_text.strip():
            continue
        box = halo_draw.textbbox((0, 0), line_text, font=font)
        text_width = box[2] - box[0]
        y = line_positions[i]
        x = (width - text_width) / 2
        halo_draw.text(
            (x, y),
            line_text,
            font=font,
            fill=QUOTE_PALETTE["halo"],
            stroke_width=max(8, int(font_size * 0.20)),
            stroke_fill=QUOTE_PALETTE["halo"],
        )

    blur_radius = max(10, int(font_size * 0.26))
    blurred_halo = text_halo.filter(ImageFilter.GaussianBlur(blur_radius))
    image = Image.alpha_composite(image, blurred_halo)
    draw = ImageDraw.Draw(image)

    # 2. Main Warm Ivory Quote Text
    for i, line_text in enumerate(visible_lines):
        if not line_text.strip():
            continue
        box = draw.textbbox((0, 0), line_text, font=font)
        text_width = box[2] - box[0]
        y = line_positions[i]
        x = (width - text_width) / 2
        draw.text(
            (x, y),
            line_text,
            font=font,
            fill=QUOTE_PALETTE["text"],
            stroke_width=max(1, int(font_size * 0.025)),
            stroke_fill=QUOTE_PALETTE["stroke"],
        )

    # 3. Saffron-Gold Quotation Marks (“ and ”) and Hairline Diamond Flourishes
    non_empty = [(i, l) for i, l in enumerate(visible_lines) if l.strip()]
    if non_empty:
        first_idx, first_text = non_empty[0]
        last_idx, last_text = non_empty[-1]

        f_box = draw.textbbox((0, 0), first_text, font=font)
        first_w = f_box[2] - f_box[0]
        first_x = (width - first_w) / 2
        first_y = line_positions[first_idx]

        l_box = draw.textbbox((0, 0), last_text, font=font)
        last_w = l_box[2] - l_box[0]
        last_x = (width - last_w) / 2
        last_y = line_positions[last_idx]

        draw.text(
            (first_x - quote_size * 0.40, first_y - quote_size * 0.08),
            "“",
            font=quote_font,
            fill=QUOTE_PALETTE["accent"],
        )
        draw.text(
            (last_x + last_w + quote_size * 0.15, last_y - quote_size * 0.08),
            "”",
            font=quote_font,
            fill=QUOTE_PALETTE["accent"],
        )

        flourish_w = int(width * 0.12)
        top_y = int(first_y - font_size * 0.80)
        bottom_y = int(last_y + line_height + font_size * 0.60)
        draw_quote_flourish(draw, width // 2, top_y, flourish_w)
        draw_quote_flourish(draw, width // 2, bottom_y, flourish_w)

    image.save(out_path)
    return out_path


def render_subtitle_overlay(
    text: str,
    out_path: Path,
    size: tuple[int, int],
    font_path: Path | None,
    h_margin_pct: float = 0.10,
    full_text: str | None = None,
    style: str = "soft_halo",
) -> Path:
    """Dedicated module for rendering standard setup subtitles."""
    try:
        from PIL import Image, ImageDraw, ImageFont, ImageFilter
    except ImportError as exc:
        raise RuntimeError("Pillow is required to render subtitle overlays") from exc

    width, height = size
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    font_size = max(24, round(height * 0.047))

    try:
        if font_path:
            font = ImageFont.truetype(str(font_path), font_size)
        else:
            font = ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()

    try:
        ascent, descent = font.getmetrics()
        line_height = ascent + descent
    except AttributeError:
        line_height = font_size

    max_line_px = width - 2 * round(width * h_margin_pct)
    wrap_target = full_text if full_text is not None else text

    full_lines = _wrap_text_px(draw, wrap_target, font, max_line_px, max_lines=2)
    total_lines = len(full_lines)
    line_gap = round(font_size * 0.35)
    total_height = total_lines * line_height + line_gap * max(0, total_lines - 1)
    y_start = height - total_height - round(height * 0.07)
    line_positions = [y_start + i * (line_height + line_gap) for i in range(total_lines)]

    if full_text is not None:
        full_line_word_counts = [len(line.split()) for line in full_lines]
        visible_words = text.split()
        visible_lines = []
        word_idx = 0
        for count in full_line_word_counts:
            line_words = visible_words[word_idx : word_idx + count]
            visible_lines.append(" ".join(line_words))
            word_idx += count
    else:
        visible_lines = _wrap_text_px(draw, text, font, max_line_px, max_lines=2)

    if style == "soft_halo":
        # 1. Soft Blackish Gradient Halo Layer for Setup Subtitles (alpha=160, 0.25 stroke mult)
        text_halo = Image.new("RGBA", size, (0, 0, 0, 0))
        halo_draw = ImageDraw.Draw(text_halo)
        for i, line_text in enumerate(visible_lines):
            if not line_text.strip():
                continue
            box = halo_draw.textbbox((0, 0), line_text, font=font)
            text_width = box[2] - box[0]
            y = line_positions[i]
            x = (width - text_width) / 2
            halo_draw.text(
                (x, y),
                line_text,
                font=font,
                fill=SUBTITLE_PALETTE["halo"],
                stroke_width=max(8, int(font_size * 0.25)),
                stroke_fill=SUBTITLE_PALETTE["halo"],
            )

        blur_radius = max(10, int(font_size * 0.26))
        blurred_halo = text_halo.filter(ImageFilter.GaussianBlur(blur_radius))
        image = Image.alpha_composite(image, blurred_halo)
        draw = ImageDraw.Draw(image)

        # 2. Main Warm Ivory Text for Setup Subtitles
        for i, line_text in enumerate(visible_lines):
            if not line_text.strip():
                continue
            box = draw.textbbox((0, 0), line_text, font=font)
            text_width = box[2] - box[0]
            y = line_positions[i]
            x = (width - text_width) / 2
            draw.text(
                (x, y),
                line_text,
                font=font,
                fill=SUBTITLE_PALETTE["text"],
                stroke_width=max(1, int(font_size * 0.025)),
                stroke_fill=SUBTITLE_PALETTE["stroke"],
            )
    else:
        # Classic Card Style (Boxed Subtitles)
        pad_x = round(font_size * 0.45)
        pad_y = round(font_size * 0.28)

        for i, line_text in enumerate(visible_lines):
            if not line_text.strip():
                continue
            box = draw.textbbox((0, 0), line_text, font=font)
            text_width = box[2] - box[0]
            y = line_positions[i]
            x = (width - text_width) / 2

            # Draw a stable background box for the current line's text
            draw.rounded_rectangle(
                [x - pad_x, y - pad_y, x + text_width + pad_x, y + line_height + pad_y],
                radius=10,
                fill=(0, 0, 0, 130),
            )
            draw.text((x, y), line_text, font=font, fill=(255, 255, 255, 255), stroke_width=1, stroke_fill=(0, 0, 0, 180))

    image.save(out_path)
    return out_path


def _wrap_text_px(
    draw: "ImageDraw.ImageDraw",
    text: str,
    font: "ImageFont.FreeTypeFont",
    max_px: int,
    max_lines: int = 2,
) -> list[str]:
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
    return lines[:max_lines]


# ── Word-by-word subtitle constants ──────────────────────────────────────────
SUBTITLE_SPEED_FACTOR: float = 0.93
SUBTITLE_WORDS_PER_STEP: int = 1    # words revealed per step (1 = true word-by-word)
SUBTITLE_FADE_DURATION: float = 0.10  # seconds for each new-word fade-in animation
SUBTITLE_FADE_FRAMES: int = 5         # blend frames per fade (higher = smoother, more files)


def _write_blended_frame(
    prev_path: Path | None,
    curr_path: Path,
    out_path: Path,
    alpha: float,
) -> None:
    """Write a blended frame between prev and curr at a given alpha (0.0=prev, 1.0=curr).

    Because both PNGs share the same locked layout, pixels for already-visible words
    are identical in both images. Only the newly added word pixels differ, so they
    are the only ones that visually fade in.
    """
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow is required for subtitle fade animation") from exc

    curr_img = Image.open(curr_path).convert("RGBA")
    if prev_path is not None and prev_path.exists():
        prev_img = Image.open(prev_path).convert("RGBA")
    else:
        prev_img = Image.new("RGBA", curr_img.size, (0, 0, 0, 0))

    result = Image.blend(prev_img, curr_img, alpha)
    result.save(out_path)


def write_word_subtitle_frames(
    text: str,
    out_dir: Path,
    scene_id: str,
    scene_duration: float,
    size: tuple[int, int],
    font_path: Path | None,
    h_margin_pct: float = 0.10,
    speed_factor: float = SUBTITLE_SPEED_FACTOR,
    words_per_step: int = SUBTITLE_WORDS_PER_STEP,
    fade_duration: float = SUBTITLE_FADE_DURATION,
    fade_frames: int = SUBTITLE_FADE_FRAMES,
) -> list[tuple[Path, float, float]]:
    """Generate cumulative word-reveal subtitle PNGs with fade-in animation for one scene.

    Each new word fades in smoothly over ``fade_duration`` seconds by blending
    from the previous state PNG into the current state PNG. Existing words are
    pixel-identical in both PNGs, so only the newly revealed word animates.

    Returns a list of (png_path, t_start, t_end) tuples ordered by t_start.
    """
    words = text.split()
    if not words:
        return []

    out_dir.mkdir(parents=True, exist_ok=True)
    n_steps = max(1, -(-len(words) // words_per_step))   # ceiling division
    t_per = scene_duration / n_steps
    frames: list[tuple[Path, float, float]] = []

    for step in range(n_steps):
        visible = " ".join(words[: (step + 1) * words_per_step])
        t_start = step * t_per * speed_factor
        if step == n_steps - 1:
            t_end = scene_duration
        else:
            t_end = (step + 1) * t_per * speed_factor
        step_dur = t_end - t_start

        # Render the full (final) PNG for this step
        curr_path = out_dir / f"{scene_id}-word-{step:04d}.png"
        write_subtitle_overlay(visible, curr_path, size, font_path, h_margin_pct, full_text=text)

        # Previous step's full PNG (used as fade-in start point)
        prev_path = out_dir / f"{scene_id}-word-{step - 1:04d}.png" if step > 0 else None

        # Clamp fade to at most half the step duration so the word is always fully visible
        actual_fade = min(fade_duration, step_dur * 0.5)
        n_fade = fade_frames if actual_fade > 0.001 else 0

        if n_fade > 0:
            fade_t_per = actual_fade / n_fade
            for f in range(n_fade):
                # alpha goes from 1/n_fade … 1.0 (never shows a fully transparent frame)
                alpha = (f + 1) / n_fade
                fade_path = out_dir / f"{scene_id}-word-{step:04d}-f{f:02d}.png"
                _write_blended_frame(prev_path, curr_path, fade_path, alpha)
                ft_start = t_start + f * fade_t_per
                ft_end = t_start + (f + 1) * fade_t_per
                frames.append((fade_path, ft_start, ft_end))
            # Hold the fully-revealed frame for the rest of the step
            frames.append((curr_path, t_start + actual_fade, t_end))
        else:
            frames.append((curr_path, t_start, t_end))

    return frames


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

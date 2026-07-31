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


def write_subtitle_overlay(
    text: str,
    out_path: Path,
    size: tuple[int, int],
    font_path: Path | None,
    h_margin_pct: float = 0.10,
    full_text: str | None = None,
) -> Path:
    """Render subtitle text as a transparent RGBA PNG overlay.

    Args:
        text:          Narration text to display.
        out_path:      Destination PNG path.
        size:          Canvas size (width, height) in pixels.
        font_path:     Path to a Devanagari-compatible .ttf/.ttc font.
        h_margin_pct:  Fraction of width reserved as left+right margin (default 10% each side).
        full_text:     If provided, the complete sentence is used to lock the layout
                       and line wrap structure, preventing text shifting as words are revealed.
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
    try:
        font = ImageFont.truetype(str(font_path), font_size) if font_path else ImageFont.load_default(size=font_size)
    except Exception:
        font = ImageFont.load_default()

    try:
        ascent, descent = font.getmetrics()
        line_height = ascent + descent
    except AttributeError:
        line_height = font_size

    # Maximum pixel width a line of text may occupy (canvas minus horizontal margins)
    max_line_px = width - 2 * round(width * h_margin_pct)

    # Use full_text if provided to lock the line wrap structure of the complete sentence
    wrap_target = full_text if full_text is not None else text
    full_lines = _wrap_text_px(draw, wrap_target, font, max_line_px)
    total_lines = len(full_lines)

    line_gap = round(font_size * 0.35)
    total_height = total_lines * line_height + line_gap * max(0, total_lines - 1)
    y_start = height - total_height - round(height * 0.07)

    # Calculate fixed vertical positions for all possible lines
    line_positions = [y_start + i * (line_height + line_gap) for i in range(total_lines)]

    # Distribute the current visible words into the pre-calculated lines
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
        visible_lines = _wrap_text_px(draw, text, font, max_line_px)

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

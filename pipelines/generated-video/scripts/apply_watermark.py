#!/usr/bin/env python3
"""
scripts/apply_watermark.py

Hides the generator's AI watermark on vertical Shorts (and standard videos),
either by covering it with a stylized circular channel badge, or by erasing it
with a radially-feathered blur that leaves no visible patch.

Usage:
  # cover it with a channel badge
  python3 scripts/apply_watermark.py -i in.mp4 -o out.mp4 --image logo.png

  # erase it with a feathered blur instead
  python3 scripts/apply_watermark.py -i in.mp4 -o out.mp4 --mode blur

  # badge, and blur underneath if the badge does not fully cover the mark
  python3 scripts/apply_watermark.py -i in.mp4 -o out.mp4 --image logo.png --mode auto

Only treat part of the timeline (e.g. the generated clips, not a rendered end
card that never had a watermark) with --start / --end.
"""

from __future__ import annotations

import argparse
import math
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageOps


# --- Watermark geometry -----------------------------------------------------
#
# Measured, not guessed. Method: extract 60 frames each from two unrelated
# scenes, average each clip temporally, high-pass each mean (mean minus its own
# sigma-8 blur), then multiply the two high-pass maps together. Moving and
# scene-specific structure cancels; the only bright structure common to both
# scenes is the watermark itself. That isolates a four-pointed sparkle whose
# bounding box is stable across thresholds from 15% to 30% of peak:
#
#   48 x 48 px centred at (600, 1160) in a 720x1280 frame
#
# A radial profile of the isolated mark shows its amplitude falling into the
# background noise floor by r = 24 px, so it has no faint tail to chase: a
# rect of the bounding box plus a small margin covers the mark completely.
WATERMARK_CENTER_REL = (600 / 720, 1160 / 1280)
WATERMARK_SIZE_REL = 48 / 720

# Derived defaults, all expressed as multiples of the mark's own size so they
# scale with the frame rather than being pinned to 720x1280.
#
# The footprint is deliberately small. Whatever removes the mark also destroys
# whatever texture was under it, so the treated area is kept barely wider than
# the mark: on a patterned surface an over-wide blur reads as a smudge long
# before it reads as "nothing happened". The ramp width is tied to sigma, not
# to the radius, because that is what actually decides whether a blur's edge
# is visible -- a weak blur needs only a few pixels to disappear into.
DELOGO_MARGIN_FRAC = 0.04  # grow the removal rect past the mark's bounding box
MARK_RADIUS_FRAC = 0.55  # the mark's own measured radius, as a fraction of side
SIGMA_FRAC_WITH_DELOGO = 0.058  # blur only has to hide delogo's seam
SIGMA_FRAC_BLUR_ONLY = 0.35  # blur alone has to dissolve the mark itself
FEATHER_PER_SIGMA = 1.5  # ramp width relative to the strongest sigma
FEATHER_MIN = 6.0  # ...but never shorter than this
FEATHER_SPAN = 1.2  # outer radius = core radius + feather * this
PATCH_PAD = 6  # keep the mask ramp clear of the crop edge


class WatermarkError(RuntimeError):
    """Raised when the watermark treatment cannot be built or applied."""


# --- Badge ------------------------------------------------------------------


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


# --- Probing ----------------------------------------------------------------


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


def ffmpeg_has_filter(name: str) -> bool:
    try:
        res = subprocess.run(
            ["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return False
    return any(line.split()[1:2] == [name] for line in res.stdout.splitlines() if line.strip())


def watermark_box(
    width: int,
    height: int,
    override_x: int | None = None,
    override_y: int | None = None,
    override_size: int | None = None,
) -> tuple[int, int, int]:
    """Return (top_left_x, top_left_y, side) of the watermark's bounding box."""
    side = override_size if override_size is not None else max(8, round(WATERMARK_SIZE_REL * width))
    if override_x is not None and override_y is not None:
        return override_x, override_y, side
    center_x = width * WATERMARK_CENTER_REL[0]
    center_y = height * WATERMARK_CENTER_REL[1]
    return round(center_x - side / 2), round(center_y - side / 2), side


def calculate_watermark_coords(
    width: int,
    height: int,
    badge_diameter: int,
    custom_x: int | None = None,
    custom_y: int | None = None,
) -> tuple[int, int]:
    """Top-left corner at which a badge of `badge_diameter` covers the mark."""
    if custom_x is not None and custom_y is not None:
        return custom_x, custom_y

    mark_x, mark_y, side = watermark_box(width, height)
    center_x = mark_x + side / 2
    center_y = mark_y + side / 2
    return round(center_x - badge_diameter / 2), round(center_y - badge_diameter / 2)


def badge_covers_watermark(
    width: int,
    height: int,
    badge_x: int,
    badge_y: int,
    badge_diameter: int,
    border_width: int,
    mark: tuple[int, int, int],
) -> tuple[bool, float]:
    """Does the badge disc fully contain the mark, with the border to spare?

    Returns (covered, shortfall_px). The badge is opaque only inside its own
    circle, so coverage is a disc-contains-disc test, not a bbox test.
    """
    mark_x, mark_y, side = mark
    mark_cx, mark_cy = mark_x + side / 2, mark_y + side / 2
    mark_r = math.hypot(side, side) / 2

    badge_cx = badge_x + badge_diameter / 2
    badge_cy = badge_y + badge_diameter / 2
    usable_r = badge_diameter / 2 - max(0, border_width)

    reach = math.hypot(mark_cx - badge_cx, mark_cy - badge_cy) + mark_r
    return reach <= usable_r, max(0.0, reach - usable_r)


# --- Feathered blur ---------------------------------------------------------


@dataclass
class BlurLevel:
    sigma: float
    radius: float
    feather: float


@dataclass
class BlurPlan:
    """A radially-graded blur that erases the mark without showing a patch.

    The naive approach — blur a region and alpha-blend it over the sharp frame
    — ghosts wherever alpha is partial, because a blurred and a sharp copy of
    the same edge are being cross-faded. Instead this stacks several blur
    levels: widest radius with the weakest sigma first, then progressively
    narrower and stronger on top, every layer's mask feathered with a
    smoothstep. Each blend is then between two *blurs* of the same content, so
    the effective sigma decays smoothly from `sigma_max` at the mark to exactly
    zero at the outer radius, and no boundary is ever crossed abruptly.
    """

    patch: tuple[int, int, int, int]  # x, y, w, h of the worked region
    center: tuple[float, float]  # mark centre, patch-local
    levels: list[BlurLevel]
    delogo: tuple[int, int, int, int] | None  # x, y, w, h
    grain: float
    grain_radius: float
    grain_feather: float
    notes: list[str] = field(default_factory=list)


def plan_blur(
    width: int,
    height: int,
    mark: tuple[int, int, int],
    use_delogo: bool,
    outer_radius: float | None = None,
    sigma_max: float | None = None,
    levels: int = 4,
    grain: float = 5.0,
    delogo_margin: int | None = None,
) -> BlurPlan:
    if levels < 1:
        raise WatermarkError("--blur-levels must be at least 1")

    mark_x, mark_y, side = mark
    mark_cx, mark_cy = mark_x + side / 2, mark_y + side / 2
    notes: list[str] = []

    if sigma_max is None:
        frac = SIGMA_FRAC_WITH_DELOGO if use_delogo else SIGMA_FRAC_BLUR_ONLY
        sigma_max = side * frac
    if sigma_max <= 0:
        raise WatermarkError("--blur-strength must be positive")

    delogo: tuple[int, int, int, int] | None = None
    if use_delogo:
        margin = (
            delogo_margin
            if delogo_margin is not None
            else max(2, round(side * DELOGO_MARGIN_FRAC))
        )
        dx, dy = mark_x - margin, mark_y - margin
        dw, dh = side + margin * 2, side + margin * 2
        # delogo interpolates from the rect's border, so the rect must sit
        # strictly inside the frame with at least one pixel to sample from.
        dx = max(1, min(dx, width - 3))
        dy = max(1, min(dy, height - 3))
        dw = min(dw, width - 1 - dx)
        dh = min(dh, height - 1 - dy)
        if dw < 2 or dh < 2:
            raise WatermarkError("watermark rect is too close to the frame edge for delogo")
        delogo = (dx, dy, dw, dh)

    # Full strength has to reach the seam delogo leaves at its rect boundary,
    # so the core radius is that rect's corner radius. With no delogo there is
    # no seam and the core only has to cover the mark itself.
    if delogo:
        dx, dy, dw, dh = delogo
        core_r = max(
            math.hypot(dx - mark_cx, dy - mark_cy),
            math.hypot(dx + dw - mark_cx, dy + dh - mark_cy),
        )
    else:
        core_r = max(4.0, MARK_RADIUS_FRAC * side)

    feather = max(FEATHER_MIN, FEATHER_PER_SIGMA * sigma_max)
    if outer_radius:
        outer_r = float(outer_radius)
        if outer_r <= core_r:
            raise WatermarkError(
                f"--blur-radius {outer_r:.0f} is inside the core radius "
                f"({core_r:.0f}px); the ramp needs room to fade out"
            )
        # Honour the requested footprint by shortening the ramp to fit it.
        feather = max(4.0, min(feather, (outer_r - core_r) / FEATHER_SPAN))
    else:
        outer_r = core_r + feather * FEATHER_SPAN

    # Worked region: the outer disc plus a little slack, clamped to the frame.
    half = outer_r + PATCH_PAD
    px0 = max(0, math.floor(mark_cx - half))
    py0 = max(0, math.floor(mark_cy - half))
    px1 = min(width, math.ceil(mark_cx + half))
    py1 = min(height, math.ceil(mark_cy + half))
    # libx264 and the 4:2:0 chroma grid both prefer even offsets and sizes.
    px0 -= px0 % 2
    py0 -= py0 % 2
    pw = (px1 - px0) - ((px1 - px0) % 2)
    ph = (py1 - py0) - ((py1 - py0) % 2)
    if pw < 8 or ph < 8:
        raise WatermarkError("worked region collapsed; check --wm-x/--wm-y/--blur-radius")
    if px1 - px0 < 2 * half or py1 - py0 < 2 * half:
        notes.append("worked region clipped by the frame edge; the ramp is asymmetric there")

    span = outer_r - core_r
    plan_levels: list[BlurLevel] = []
    for i in range(levels):
        # Widest and weakest first; narrowest and strongest composited last.
        radius = outer_r - span * (i / (levels - 1)) if levels > 1 else outer_r
        sigma = sigma_max * ((i + 1) / levels)
        if sigma < 0.3:
            continue
        plan_levels.append(BlurLevel(sigma=sigma, radius=radius, feather=feather))
    if not plan_levels:
        raise WatermarkError("every blur level rounded away; raise --blur-strength")

    return BlurPlan(
        patch=(px0, py0, pw, ph),
        center=(mark_cx - px0, mark_cy - py0),
        levels=plan_levels,
        delogo=delogo,
        grain=max(0.0, grain),
        grain_radius=outer_r,
        grain_feather=feather,
        notes=notes,
    )


def _alpha_expr(cx: float, cy: float, radius: float, feather: float) -> str:
    """geq luma: 255 inside `radius - feather`, 0 at `radius`, smoothstep between.

    Written as a single expression rather than st()/ld() because ';' would have
    to be escaped through the filtergraph parser; the term is cheap enough to
    repeat on a region this small.
    """
    u = f"clip(({radius:.3f}-hypot(X-{cx:.3f},Y-{cy:.3f}))/{feather:.3f},0,1)"
    return f"255*{u}*{u}*(3-2*{u})"


def _enable_suffix(start: float | None, end: float | None) -> str:
    if start is None and end is None:
        return ""
    lo = 0.0 if start is None else start
    if end is None:
        return f":enable='gte(t,{lo:g})'"
    return f":enable='between(t,{lo:g},{end:g})'"


def build_blur_chains(
    plan: BlurPlan,
    src: str,
    out: str,
    start: float | None,
    end: float | None,
) -> list[str]:
    """Filterchains that take `[src]` to `[out]` with the mark erased."""
    chains: list[str] = []
    gate = _enable_suffix(start, end)
    cx, cy = plan.center
    px, py, pw, ph = plan.patch
    n = len(plan.levels)

    stage = src
    if plan.delogo:
        dx, dy, dw, dh = plan.delogo
        chains.append(f"[{stage}]delogo=x={dx}:y={dy}:w={dw}:h={dh}{gate}[wm_de]")
        stage = "wm_de"

    # One copy stays whole as the canvas; one is cropped into the worked patch.
    chains.append(f"[{stage}]split=2[wm_base][wm_full]")
    chains.append(f"[wm_full]crop={pw}:{ph}:{px}:{py}[wm_patch]")

    # The patch feeds the composite base, plus a blur source and a mask source
    # per level (and two more if grain is on).
    fan = ["wm_acc0"] + [f"wm_b{i}" for i in range(n)] + [f"wm_m{i}" for i in range(n)]
    if plan.grain > 0:
        fan.append("wm_gm")
    chains.append(f"[wm_patch]split={len(fan)}" + "".join(f"[{lbl}]" for lbl in fan))

    for i, level in enumerate(plan.levels):
        chains.append(
            f"[wm_b{i}]gblur=sigma={level.sigma:.3f}:steps=3,format=yuva420p[wm_bf{i}]"
        )
        chains.append(
            f"[wm_m{i}]format=gray,"
            f"geq=lum='{_alpha_expr(cx, cy, level.radius, level.feather)}'[wm_mf{i}]"
        )
        chains.append(f"[wm_bf{i}][wm_mf{i}]alphamerge[wm_l{i}]")
        chains.append(f"[wm_acc{i}][wm_l{i}]overlay=0:0:format=auto[wm_acc{i + 1}]")

    acc = f"wm_acc{n}"
    if plan.grain > 0:
        # Blurring strips the sensor grain and leaves a plastic-looking patch.
        # Put a little temporal noise back, fading out on the same ramp so the
        # grain itself does not draw a boundary.
        chains.append(f"[{acc}]split=2[wm_gs][wm_gn]")
        chains.append(
            f"[wm_gn]noise=alls={plan.grain:.0f}:allf=t+u,format=yuva420p[wm_gnf]"
        )
        chains.append(
            f"[wm_gm]format=gray,"
            f"geq=lum='{_alpha_expr(cx, cy, plan.grain_radius, plan.grain_feather)}'[wm_gmf]"
        )
        chains.append("[wm_gnf][wm_gmf]alphamerge[wm_gl]")
        chains.append("[wm_gs][wm_gl]overlay=0:0:format=auto[wm_gout]")
        acc = "wm_gout"

    # The patch's rim is untouched source, so it can go back at full opacity.
    chains.append(f"[wm_base][{acc}]overlay={px}:{py}:format=auto{gate}[{out}]")
    return chains


def build_debug_chain(plan: BlurPlan, src: str, out: str) -> list[str]:
    px, py, pw, ph = plan.patch
    cx, cy = plan.center
    parts = [f"[{src}]drawbox=x={px}:y={py}:w={pw}:h={ph}:color=cyan@0.8:t=1"]
    if plan.delogo:
        dx, dy, dw, dh = plan.delogo
        parts.append(f"drawbox=x={dx}:y={dy}:w={dw}:h={dh}:color=red@0.9:t=1")
    outer = plan.levels[0].radius
    parts.append(
        f"drawbox=x={px + cx - outer:.0f}:y={py + cy - outer:.0f}"
        f":w={outer * 2:.0f}:h={outer * 2:.0f}:color=yellow@0.6:t=1"
    )
    return [",".join(parts) + f"[{out}]"]


# --- Orchestration ----------------------------------------------------------


def apply_watermark(
    input_video: Path,
    output_video: Path,
    image_path: Path | None = None,
    mode: str = "auto",
    badge_size: int = 80,
    x: int | None = None,
    y: int | None = None,
    border_width: int = 3,
    blur_radius: float | None = None,
    blur_strength: float | None = None,
    blur_levels: int = 4,
    blur_grain: float = 5.0,
    delogo_margin: int | None = None,
    use_delogo: bool = True,
    start: float | None = None,
    end: float | None = None,
    wm_x: int | None = None,
    wm_y: int | None = None,
    wm_size: int | None = None,
    preview: float | None = None,
    show_region: bool = False,
) -> None:
    if not input_video.exists():
        raise FileNotFoundError(f"Input video not found: {input_video}")
    if image_path is not None and not image_path.exists():
        raise FileNotFoundError(f"Watermark image not found: {image_path}")

    if mode in {"badge", "both"} and image_path is None:
        raise WatermarkError(f"--mode {mode} needs --image")
    chose_for_us = mode == "auto"
    if chose_for_us:
        mode = "badge" if image_path is not None else "blur"

    output_video.parent.mkdir(parents=True, exist_ok=True)
    w, h = get_video_dimensions(input_video)
    mark = watermark_box(w, h, wm_x, wm_y, wm_size)

    badge_xy: tuple[int, int] | None = None
    if mode in {"badge", "both"}:
        badge_xy = calculate_watermark_coords(w, h, badge_size, x, y)
        covered, shortfall = badge_covers_watermark(
            w, h, badge_xy[0], badge_xy[1], badge_size, border_width, mark
        )
        if mode == "badge" and not covered:
            if chose_for_us:
                # The badge is not actually sitting over the mark, so covering
                # alone would leave the sparkle showing. Blur underneath too.
                mode = "both"
                print(
                    f"  badge misses the mark by {shortfall:.0f}px — blurring "
                    f"underneath as well (--mode badge to cover only)"
                )
            else:
                print(
                    f"  warning: badge misses the mark by {shortfall:.0f}px, so the "
                    f"watermark will still show; raise --badge-size or use --mode both"
                )
        elif mode == "both" and covered and not chose_for_us:
            print("  note: the badge already covers the mark; blurring underneath anyway")

    plan: BlurPlan | None = None
    if mode in {"blur", "both"}:
        delogo_ok = use_delogo and ffmpeg_has_filter("delogo")
        if use_delogo and not delogo_ok:
            print("  note: this ffmpeg has no delogo filter; falling back to blur alone")
        plan = plan_blur(
            width=w,
            height=h,
            mark=mark,
            use_delogo=delogo_ok,
            outer_radius=blur_radius,
            sigma_max=blur_strength,
            levels=blur_levels,
            grain=blur_grain,
            delogo_margin=delogo_margin,
        )
        for note in plan.notes:
            print(f"  note: {note}")

    with tempfile.TemporaryDirectory() as tmpdir:
        chains: list[str] = []
        extra_inputs: list[str] = []
        stage = "0:v"

        if plan is not None:
            chains += build_blur_chains(plan, stage, "wm_blurred", start, end)
            stage = "wm_blurred"

        if badge_xy is not None and image_path is not None:
            badge_canvas = make_circular_badge(
                image_path=image_path, diameter=badge_size, border_width=border_width
            )
            pad_x, pad_y = badge_canvas.info.get("badge_offset", (0, 0))
            temp_badge_path = Path(tmpdir) / "badge_overlay.png"
            badge_canvas.save(temp_badge_path, format="PNG")
            extra_inputs = ["-i", str(temp_badge_path)]
            overlay_x = badge_xy[0] - pad_x
            overlay_y = badge_xy[1] - pad_y
            chains.append(
                f"[{stage}][1:v]overlay={overlay_x}:{overlay_y}:format=auto"
                f"{_enable_suffix(start, end)}[wm_badged]"
            )
            stage = "wm_badged"

        if show_region:
            if plan is None:
                raise WatermarkError("--show-region needs a blur mode")
            chains += build_debug_chain(plan, stage, "wm_debug")
            stage = "wm_debug"

        if not chains:
            raise WatermarkError("nothing to do: no badge and no blur")

        chains.append(f"[{stage}]format=yuv420p[wm_out]")
        filter_complex = ";".join(chains)

        cmd = ["ffmpeg", "-y"]
        if preview is not None:
            cmd += ["-ss", f"{preview:g}"]
        cmd += ["-i", str(input_video), *extra_inputs]
        cmd += ["-filter_complex", filter_complex, "-map", "[wm_out]"]
        if preview is not None:
            cmd += ["-frames:v", "1", str(output_video)]
        else:
            cmd += [
                "-map", "0:a?",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-preset", "medium",
                "-crf", "18",
                "-movflags", "+faststart",
                "-c:a", "copy",
                str(output_video),
            ]

        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise WatermarkError(f"FFmpeg failed with code {res.returncode}:\n{res.stderr}")

    mark_desc = f"mark {mark[2]}x{mark[2]} at ({mark[0]},{mark[1]})"
    if plan is not None:
        px, py, pw, ph = plan.patch
        sigmas = "/".join(f"{lv.sigma:.1f}" for lv in plan.levels)
        radii = "/".join(f"{lv.radius:.0f}" for lv in plan.levels)
        print(
            f"  {mark_desc}; delogo={'on' if plan.delogo else 'off'}; "
            f"region {pw}x{ph} at ({px},{py}); sigma {sigmas} at radius {radii}; "
            f"grain {plan.grain:.0f}"
        )
    else:
        print(f"  {mark_desc}; badge {badge_size}px at {badge_xy}")
    if start is not None or end is not None:
        print(f"  applied only between t={start or 0:g}s and t={end if end else 'end'}")
    print(f"✓ Watermark {'previewed' if preview is not None else 'masked'}: {output_video}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Hide the AI watermark with a circular channel badge, a feathered blur, or both."
    )
    parser.add_argument("--input", "-i", type=Path, required=True, help="Path to input MP4 video")
    parser.add_argument("--output", "-o", type=Path, required=True, help="Path to output MP4 video")
    parser.add_argument(
        "--image", "-img", type=Path, default=None, help="Logo/avatar image for the badge"
    )
    parser.add_argument(
        "--mode",
        choices=("auto", "badge", "blur", "both"),
        default="auto",
        help="auto: badge if --image is given (blurring too if the badge misses the mark), "
             "else blur. badge: cover only. blur: erase only. both: blur then badge.",
    )
    parser.add_argument("--badge-size", "--size", type=int, default=80, help="Badge diameter in px (default: 80)")
    parser.add_argument("--x", type=int, default=None, help="Custom badge top-left X")
    parser.add_argument("--y", type=int, default=None, help="Custom badge top-left Y")
    parser.add_argument("--border-width", type=int, default=3, help="Badge border width in px (default: 3)")

    blur = parser.add_argument_group("feathered blur")
    blur.add_argument("--blur-radius", type=float, default=None,
                      help="Outer radius in px where the blur has faded to nothing (default: auto from mark size)")
    blur.add_argument("--blur-strength", type=float, default=None,
                      help="Gaussian sigma at the mark (default: auto; higher without delogo)")
    blur.add_argument("--blur-levels", type=int, default=4,
                      help="Blur levels stacked to grade the falloff (default: 4)")
    blur.add_argument("--blur-grain", type=float, default=5.0,
                      help="Grain put back inside the blurred patch, 0 disables (default: 5)")
    blur.add_argument("--delogo-margin", type=int, default=None,
                      help="Grow the removal rect this many px past the mark (default: auto)")
    blur.add_argument("--no-delogo", dest="use_delogo", action="store_false",
                      help="Skip delogo and dissolve the mark with blur alone")

    region = parser.add_argument_group("region and timing")
    region.add_argument("--start", type=float, default=None, help="Treat only from this timestamp (s)")
    region.add_argument("--end", type=float, default=None, help="Treat only up to this timestamp (s)")
    region.add_argument("--wm-x", type=int, default=None, help="Override the mark's top-left X")
    region.add_argument("--wm-y", type=int, default=None, help="Override the mark's top-left Y")
    region.add_argument("--wm-size", type=int, default=None, help="Override the mark's bounding-box side in px")
    region.add_argument("--preview", type=float, default=None, metavar="T",
                        help="Write a single treated frame at T seconds instead of a clip")
    region.add_argument("--show-region", action="store_true",
                        help="Draw the delogo rect, the outer radius and the worked region")

    args = parser.parse_args()
    try:
        apply_watermark(
            input_video=args.input,
            output_video=args.output,
            image_path=args.image,
            mode=args.mode,
            badge_size=args.badge_size,
            x=args.x,
            y=args.y,
            border_width=args.border_width,
            blur_radius=args.blur_radius,
            blur_strength=args.blur_strength,
            blur_levels=args.blur_levels,
            blur_grain=args.blur_grain,
            delogo_margin=args.delogo_margin,
            use_delogo=args.use_delogo,
            start=args.start,
            end=args.end,
            wm_x=args.wm_x,
            wm_y=args.wm_y,
            wm_size=args.wm_size,
            preview=args.preview,
            show_region=args.show_region,
        )
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

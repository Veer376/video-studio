#!/usr/bin/env python3
"""Apply optional KathaMind visual texture as a post-production pass.

The script intentionally works *after* subtitles/BGM/watermark treatment so a
chosen effect can be auditioned without rebuilding the production timeline.
Audio is stream-copied unchanged.

Modes are deliberately restrained:

  micro-jitter  Sparse 1-3 px impact-like frame movement.
  glitter       Sparse tiny, low-opacity specular twinkles; no camera movement.
  combo         Micro-jitter plus the sparse twinkles.
  film-weave    Near-imperceptible continuous gate weave plus fine grain.

Nothing is selected by default for the final master.  Use short previews first.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


class TextureError(RuntimeError):
    pass


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise TextureError((result.stderr or result.stdout)[-6000:])
    return result


def probe(path: Path) -> dict:
    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,r_frame_rate",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ]
    )
    data = json.loads(result.stdout)
    stream = data["streams"][0]
    return {
        "width": int(stream["width"]),
        "height": int(stream["height"]),
        "fps": stream["r_frame_rate"],
        "duration": float(data["format"]["duration"]),
    }


def even(value: float) -> int:
    n = max(2, round(value))
    return n if n % 2 == 0 else n + 1


def ff_num(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def escaped_if_window(start: float, end: float, body: str) -> str:
    # Commas inside crop x/y expressions must be escaped so they are not parsed
    # as filter separators by libavfilter.
    return f"if(between(t\\,{ff_num(start)}\\,{ff_num(end)})\\,{body}\\,0)"


def jitter_schedule(duration: float, seed: int) -> list[tuple[float, float, float, float, float, float]]:
    rng = random.Random(seed)
    events = []
    t = 1.4
    while t < duration - 0.2:
        t += rng.uniform(2.2, 4.6)
        if t >= duration - 0.15:
            break
        length = rng.uniform(0.09, 0.17)
        amp_x = rng.uniform(1.2, 2.6)
        amp_y = rng.uniform(0.7, 1.8)
        hz_x = rng.uniform(13.0, 19.0)
        hz_y = rng.uniform(11.0, 17.0)
        events.append((t, min(duration, t + length), amp_x, amp_y, hz_x, hz_y))
    return events


def jitter_filters(width: int, height: int, duration: float, seed: int) -> list[str]:
    scale_w = even(width * 1.0105)
    scale_h = even(height * 1.0105)
    base_x = (scale_w - width) / 2
    base_y = (scale_h - height) / 2
    x_terms: list[str] = []
    y_terms: list[str] = []
    for start, end, amp_x, amp_y, hz_x, hz_y in jitter_schedule(duration, seed):
        local_x = f"{ff_num(amp_x)}*sin(2*PI*{ff_num(hz_x)}*(t-{ff_num(start)}))"
        local_y = f"{ff_num(amp_y)}*sin(2*PI*{ff_num(hz_y)}*(t-{ff_num(start)})+1.2)"
        x_terms.append(escaped_if_window(start, end, local_x))
        y_terms.append(escaped_if_window(start, end, local_y))
    x_expr = ff_num(base_x) + ("+" + "+".join(x_terms) if x_terms else "")
    y_expr = ff_num(base_y) + ("+" + "+".join(y_terms) if y_terms else "")
    return [
        f"scale={scale_w}:{scale_h}:flags=lanczos",
        f"crop={width}:{height}:x='{x_expr}':y='{y_expr}'",
    ]


def film_weave_filters(width: int, height: int) -> list[str]:
    scale_w = even(width * 1.008)
    scale_h = even(height * 1.008)
    base_x = (scale_w - width) / 2
    base_y = (scale_h - height) / 2
    x = f"{ff_num(base_x)}+0.65*sin(2*PI*0.71*t)+0.35*sin(2*PI*1.83*t)"
    y = f"{ff_num(base_y)}+0.55*sin(2*PI*0.93*t+0.7)"
    return [
        f"scale={scale_w}:{scale_h}:flags=lanczos",
        f"crop={width}:{height}:x='{x}':y='{y}'",
        "noise=alls=2.2:allf=t+u",
    ]


def glitter_schedule(duration: float, width: int, height: int, seed: int) -> list[tuple[int, int, int, float, float, float]]:
    """Sparse specular twinkles, biased away from the subtitle-safe lower band."""
    rng = random.Random(seed + 991)
    events = []
    t = 0.8
    while t < duration - 0.1:
        t += rng.uniform(0.55, 1.35)
        if t >= duration - 0.08:
            break
        # Keep flecks away from the bottom caption zone. Bias some to the outer
        # thirds so they read as material/atmospheric texture, not face effects.
        if rng.random() < 0.62:
            if rng.random() < 0.5:
                x = rng.randint(round(width * 0.05), round(width * 0.30))
            else:
                x = rng.randint(round(width * 0.70), round(width * 0.95))
        else:
            x = rng.randint(round(width * 0.08), round(width * 0.92))
        y = rng.randint(round(height * 0.08), round(height * 0.68))
        size = rng.choice((2, 2, 3, 3, 4))
        life = rng.uniform(0.07, 0.18)
        alpha = rng.uniform(0.08, 0.17)
        events.append((x, y, size, t, min(duration, t + life), alpha))
    return events


def glitter_filters(duration: float, width: int, height: int, seed: int) -> list[str]:
    filters: list[str] = []
    for x, y, size, start, end, alpha in glitter_schedule(duration, width, height, seed):
        # A tiny cross rather than a large star sprite. At these alpha values it
        # behaves as a brief specular glint instead of decorative "magic".
        half = max(2, size + 1)
        horizontal_x = max(0, x - half)
        vertical_y = max(0, y - half)
        filters.append(
            "drawbox="
            f"x={horizontal_x}:y={y}:w={half * 2 + 1}:h=1:"
            f"color=white@{alpha:.3f}:t=fill:enable='between(t,{ff_num(start)},{ff_num(end)})'"
        )
        filters.append(
            "drawbox="
            f"x={x}:y={vertical_y}:w=1:h={half * 2 + 1}:"
            f"color=white@{alpha:.3f}:t=fill:enable='between(t,{ff_num(start)},{ff_num(end)})'"
        )
    return filters


def build_filter(mode: str, width: int, height: int, duration: float, seed: int) -> str:
    filters: list[str] = []
    if mode in {"micro-jitter", "combo"}:
        filters.extend(jitter_filters(width, height, duration, seed))
    elif mode == "film-weave":
        filters.extend(film_weave_filters(width, height))

    if mode in {"glitter", "combo"}:
        filters.extend(glitter_filters(duration, width, height, seed))

    filters.extend(["setsar=1", "format=yuv420p"])
    return ",".join(filters)


def apply(args: argparse.Namespace) -> None:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise TextureError("ffmpeg and ffprobe are required")

    input_path = args.input.expanduser().resolve()
    output_path = args.output.expanduser().resolve()
    if not input_path.is_file():
        raise TextureError(f"Input does not exist: {input_path}")
    if input_path == output_path:
        raise TextureError("Output must differ from input")
    if output_path.exists() and not args.force:
        raise TextureError(f"Output exists; pass --force to replace: {output_path}")

    info = probe(input_path)
    start = max(0.0, args.start)
    if start >= info["duration"]:
        raise TextureError("--start is beyond the input duration")
    duration = info["duration"] - start
    if args.duration is not None:
        if args.duration <= 0:
            raise TextureError("--duration must be positive")
        duration = min(duration, args.duration)

    vf = build_filter(args.mode, info["width"], info["height"], duration, args.seed)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-v", "error", "-y"]
    if start > 0:
        cmd += ["-ss", ff_num(start)]
    cmd += ["-i", str(input_path), "-t", ff_num(duration), "-vf", vf]
    cmd += [
        "-map", "0:v:0", "-map", "0:a?",
        "-c:v", "libx264", "-preset", args.preset, "-crf", str(args.crf),
        "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart",
        str(output_path),
    ]

    print(f"Mode: {args.mode}")
    print(f"Input: {input_path}")
    print(f"Output: {output_path}")
    print(f"Range: {start:.3f}s + {duration:.3f}s")
    if args.mode in {"micro-jitter", "combo"}:
        print(f"Jitter bursts: {len(jitter_schedule(duration, args.seed))}")
    if args.mode in {"glitter", "combo"}:
        print(f"Glitter events: {len(glitter_schedule(duration, info['width'], info['height'], args.seed))}")
    if args.dry_run:
        print("FFmpeg command:")
        print(" ".join(shlex.quote(part) for part in cmd))
        return

    run(cmd)
    out = probe(output_path)
    if abs(out["duration"] - duration) > 0.12:
        raise TextureError(f"Output duration mismatch: {out['duration']:.3f}s vs {duration:.3f}s")
    print(f"✓ Texture preview rendered: {output_path}")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", "-i", type=Path, required=True)
    p.add_argument("--output", "-o", type=Path, required=True)
    p.add_argument(
        "--mode",
        choices=("micro-jitter", "glitter", "combo", "film-weave"),
        required=True,
    )
    p.add_argument("--start", type=float, default=0.0, help="Preview start timestamp")
    p.add_argument("--duration", type=float, default=None, help="Optional preview duration")
    p.add_argument("--seed", type=int, default=3107)
    p.add_argument("--crf", type=int, default=18)
    p.add_argument("--preset", default="veryfast")
    p.add_argument("--force", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    return p


def main() -> int:
    try:
        apply(parser().parse_args())
    except (TextureError, json.JSONDecodeError, KeyError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

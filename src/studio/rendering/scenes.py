"""
Stage 2 of render pipeline: Render scene clips with Ken Burns motion, burn in word-by-word
Pillow-rendered subtitle overlays, and concatenate them with crossfade transitions.

This implementation uses transparent PNGs rendered via Pillow and overlays them onto the clips
using FFmpeg's overlay filter, bypassing the need for FFmpeg's libass library.

Usage:
    python3 render_video.py --project-dir library/2026-08-01_krishna-motivation
"""
import os
import sys

# On macOS, ensure Homebrew's library path is in DYLD_LIBRARY_PATH so Pillow can load libraqm for Devanagari text shaping
if sys.platform == "darwin" and "/opt/homebrew/lib" not in os.environ.get("DYLD_LIBRARY_PATH", ""):
    os.environ["DYLD_LIBRARY_PATH"] = "/opt/homebrew/lib" + (":" + os.environ["DYLD_LIBRARY_PATH"] if "DYLD_LIBRARY_PATH" in os.environ else "")
    try:
         os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as e:
         sys.stderr.write(f"Warning: Failed to set DYLD_LIBRARY_PATH and re-exec: {e}\n")

import argparse
import json
import math
import re
import shutil
import subprocess
from pathlib import Path

from studio.subtitles.subtitles import detect_devanagari_font_path as detect_devanagari_font, subtitle_enable_expr, write_subtitle_overlay

CROSSFADE_DURATION = 0.4   # seconds of crossfade between scenes
KEN_BURNS_ZOOM     = 0.06  # max additional zoom (6%) applied over scene duration
CLOSING_TAIL_EXTENSION = 2.0   # seconds added to final scene clip for post-narration reflection
CLOSING_FADE_DURATION = 4.0    # total duration of fade out to black
RENDER_WIDTH = 1920
RENDER_HEIGHT = 1080
RENDER_FPS = 30


class FFmpegError(RuntimeError):
    pass


def ffmpeg(*args: str) -> None:
    """Run an ffmpeg command, raise FFmpegError if it fails."""
    cmd = ["ffmpeg", "-y"] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        tail = (result.stderr or result.stdout)[-4000:]
        raise FFmpegError(f"ffmpeg failed:\n{tail}")


def _bigram_sim(a: str, b: str) -> float:
    """Character bigram Jaccard similarity (local copy for renderer use)."""
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    # Strip nukta and halant for Devanagari normalization
    def _norm(s):
        s = re.sub(r'[>*"\'.,!?।—…]', '', s)
        return s.replace('\u094d', '').replace('\u093c', '')
    a, b = _norm(a), _norm(b)
    bg_a = {a[i:i+2] for i in range(len(a) - 1)}
    bg_b = {b[i:i+2] for i in range(len(b) - 1)}
    if not bg_a or not bg_b:
        return 1.0 if a == b else 0.0
    return len(bg_a & bg_b) / len(bg_a | bg_b)


def assign_words_to_scenes(words: list[dict], scenes: list[dict]) -> dict[int, list[dict]]:
    """
    Assign each Groq word to exactly one scene using a greedy single-pass assignment.
    Each word is assigned to the first scene (by scene order) whose [start_t, end_t) window
    contains the word's start time. Returns dict mapping scene index -> list of assigned words.
    Guarantees zero word duplication across adjacent scenes.
    """
    scene_windows = []
    for idx, scene in enumerate(scenes):
        start_t = scene.get("start_time")
        end_t = scene.get("end_time")
        if start_t is not None and end_t is not None:
            scene_windows.append((float(start_t), float(end_t), idx))
    scene_windows.sort(key=lambda x: x[0])

    assignment: dict[int, list[dict]] = {i: [] for i in range(len(scenes))}
    scene_idx = 0
    m = len(scene_windows)

    if m == 0:
        return assignment

    for word in words:
        w_start = float(word["start"])
        while scene_idx < m - 1 and w_start >= scene_windows[scene_idx][1]:
            scene_idx += 1
        start_t, end_t, real_idx = scene_windows[scene_idx]
        if w_start >= start_t and w_start < end_t:
            assignment[real_idx].append(word)

    return assignment


def generate_scene_subtitle_frames(
    scene: dict,
    words: list[dict],
    out_dir: Path,
    size: tuple[int, int],
    font_path: Path | None,
    clip_duration: float = 0.0,
    prev_scene_ended_with_quote: bool = False,
    style: str = "soft_halo",
    scene_words: list[dict] | None = None,
) -> list[tuple[Path, float, float]]:
    """
    Generate transparent PNG overlays for each word in the scene using Pillow.
    Timings are calculated relative to the scene's start time (0.0s).

    If scene["text"] contains ">", the words before ">" are rendered as normal
    bottom subtitles and words from ">" onwards switch to the centered quote layout.

    n_setup is determined by bigram-matching the first quote word against scene_words
    (Fix 7), so it is robust to Groq tokenization variance.

    Quote display text is drawn from script text, not Groq transcription (Fix 8),
    preserving correct Sanskrit, proper nouns, and stylized spellings.
    """
    import unicodedata as _ud
    start_t = scene["start_time"]
    end_t = scene["end_time"]
    scene_id = scene["id"]
    scene_text = scene.get("text", "")

    has_quote_marker = ">" in scene_text

    # Filter words belonging to this scene's time window if pre-assigned list not provided
    if scene_words is None:
        scene_words = [
            w for w in words
            if w["start"] >= start_t and w["start"] < end_t
        ]
    if not scene_words:
        return []

    # --- Fix 7: Determine n_setup by bigram-matching first quote word ---
    if has_quote_marker:
        quote_raw = scene_text.split(">", 1)[1].strip()
        quote_first_word = re.sub(r'[*"\'.,!?।—…\[\]]', '', quote_raw.split()[0]).strip() if quote_raw.split() else ""
        n_setup = 0
        if quote_first_word:
            for k, gw in enumerate(scene_words):
                if _bigram_sim(gw["word"], quote_first_word) >= 0.55:
                    n_setup = k
                    break
            else:
                # Fallback to text.split() count if no bigram match found
                prefix_part = scene_text.split(">", 1)[0].strip()
                n_setup = len(prefix_part.split()) if prefix_part else 0
        else:
            n_setup = 0
    else:
        n_setup = 0

    # --- Fix 8: Prepare script-side quote words for display ---
    if has_quote_marker:
        quote_script_raw = scene_text.split(">", 1)[1].strip()
        quote_script_words = re.sub(r'[*"\'\[\]]', '', quote_script_raw).split()
        quote_groq_words = scene_words[n_setup:]
    else:
        quote_script_words = []
        quote_groq_words = []

    # Build full_text locks (used for sizing/layout)
    setup_full_text = " ".join(w["word"] for w in scene_words[:n_setup]) if n_setup else ""
    quote_full_text = " ".join(quote_script_words) if has_quote_marker and quote_script_words else " ".join(w["word"] for w in scene_words)

    frames = []
    cumulative_setup: list[str] = []
    cumulative_quote: list[str] = []

    for i, word in enumerate(scene_words):
        is_quote_frame = has_quote_marker and i >= n_setup

        if is_quote_frame:
            # Map Groq word position to script word position proportionally
            quote_pos = i - n_setup
            if quote_script_words and quote_groq_words:
                ratio = quote_pos / max(len(quote_groq_words) - 1, 1)
                script_pos = min(round(ratio * (len(quote_script_words) - 1)), len(quote_script_words) - 1)
                display_word = quote_script_words[script_pos]
            else:
                display_word = word["word"].strip()
            # Avoid duplicating last word when Groq has more tokens than script
            if not cumulative_quote or cumulative_quote[-1] != display_word:
                cumulative_quote.append(display_word)
            visible_text = " ".join(cumulative_quote)
            full_text = quote_full_text
        else:
            word_str = word["word"].strip()
            cumulative_setup.append(word_str)
            visible_text = " ".join(cumulative_setup)
            full_text = setup_full_text if setup_full_text else quote_full_text

        # Calculate overlay start/end times relative to the scene's start (0.0s)
        t_start = max(0.0, word["start"] - start_t)
        if i < len(scene_words) - 1:
            t_end = max(0.0, scene_words[i + 1]["start"] - start_t)
        else:
            t_end = end_t - start_t

        if t_end <= t_start + 0.001:
            continue

        png_path = out_dir / f"{scene_id}-word-{i:04d}.png"
        write_subtitle_overlay(
            text=visible_text,
            out_path=png_path,
            size=size,
            font_path=font_path,
            full_text=full_text,
            is_quote=is_quote_frame,
            style=style,
        )
        frames.append((png_path, t_start, t_end))

    # Prepend the timed vignette overlay for the quote portion.
    # Extends to clip_duration to guarantee continuous dark background during crossfades.
    if has_quote_marker and scene_words:
        if n_setup == 0 or prev_scene_ended_with_quote:
            quote_t_start = 0.0
        else:
            quote_t_start = max(0.0, scene_words[n_setup]["start"] - start_t) if n_setup < len(scene_words) else 0.0
        quote_t_end = max(clip_duration, end_t - start_t)
        if quote_t_end > quote_t_start + 0.001:
            vignette_png = out_dir / f"{scene_id}-vignette.png"
            _generate_vignette_overlay(vignette_png, size, center_alpha=185)
            frames.insert(0, (vignette_png, quote_t_start, quote_t_end))

    return frames


def _generate_vignette_overlay(out_path: Path, size: tuple[int, int], center_alpha: int = 185) -> None:
    """Generate a standalone RGBA vignette overlay PNG (black with Hermite radial alpha)."""
    try:
        from PIL import Image
    except ImportError:
        return

    width, height = size
    gw, gh = 300, 300
    low = Image.new("L", (gw, gh), 0)
    pix = low.load()
    cx, cy = gw / 2.0, gh / 2.0
    max_r = math.sqrt(cx * cx + cy * cy)

    for y in range(gh):
        for x in range(gw):
            dist = (math.sqrt((x - cx) ** 2 + (y - cy) ** 2) / max_r) * 0.55
            d = max(0.0, min(1.0, dist))
            smooth_val = 1.0 - (3.0 * (d ** 2) - 2.0 * (d ** 3))
            pix[x, y] = int(center_alpha * smooth_val)

    grad_mask = low.resize((width, height), Image.Resampling.BICUBIC)
    dark = Image.new("RGBA", (width, height), (0, 0, 0, 255))
    dark.putalpha(grad_mask)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    dark.save(out_path)


def render_scene_clip(
    image_path: Path,
    duration: float,
    out_path: Path,
    width: int,
    height: int,
    fps: int,
    subtitle_frames: list[tuple[Path, float, float]],
    no_motion: bool = False,
) -> None:
    """
    Render a single scene image as a silent MP4 clip, optionally applying Ken Burns slow zoom,
    and burn in word-by-word subtitle overlays using FFmpeg's overlay filter.
    """
    if no_motion:
        # Static scaling and cropping with no motion (prevents trembling/shaking completely)
        vf = (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height}"
        )
    else:
        # Render Ken Burns motion above final resolution to reduce pixel-step jitter.
        # 2x is the default speed/quality tradeoff for 1080p production renders.
        frames = max(1, round(duration * fps))
        step = KEN_BURNS_ZOOM / max(1, frames - 1)

        hires_w = width * 2
        hires_h = height * 2

        zoom_expr = f"1.0+on*{step:.8f}"
        x_expr = "(iw-iw/zoom)/2"
        y_expr = "(ih-ih/zoom)/2"

        vf = (
            f"scale={hires_w}:{hires_h}:force_original_aspect_ratio=increase,"
            f"crop={hires_w}:{hires_h},"
            f"zoompan=z='{zoom_expr}':x='{x_expr}':y='{y_expr}':d={frames}:s={hires_w}x{hires_h}:fps={fps},"
            f"scale={width}:{height}"
        )

    args = ["-loop", "1", "-i", str(image_path)]

    if subtitle_frames:
        # Extend inputs for each subtitle frame PNG, locking their framerate to the video's fps to avoid flickering
        for png_path, _, _ in subtitle_frames:
            args.extend(["-loop", "1", "-framerate", str(fps), "-i", str(png_path)])

        chains: list[str] = []
        prev = "[kbv]"
        kb_vf = f"{vf}[kbv]"
        
        for idx, (png_path, t_start, t_end) in enumerate(subtitle_frames, start=1):
            out_label = f"[ov{idx}]"
            if png_path.name.endswith("-vignette.png"):
                fade_filters = []
                # Fade in only if quote starts after scene start (t_start > 0.05s)
                if t_start > 0.05:
                    fade_in_d = min(0.8, (t_end - t_start) / 2)
                    fade_filters.append(f"fade=t=in:st={t_start:.4f}:d={fade_in_d:.2f}:alpha=1")
                # Fade out ONLY if quote genuinely ends before end of clip
                if t_end < (duration - 0.05):
                    fade_out_d = min(0.8, (t_end - t_start) / 2)
                    fade_out_st = max(t_start, t_end - fade_out_d)
                    fade_filters.append(f"fade=t=out:st={fade_out_st:.4f}:d={fade_out_d:.2f}:alpha=1")

                filter_str = ",".join(["format=rgba"] + fade_filters)
                filter_prefix = f"{filter_str}," if filter_str else ""
                vignette_chain = (
                    f"[{idx}:v]{filter_prefix}format=rgba[vig{idx}];"
                    f"{prev}[vig{idx}]overlay=0:0:enable='{subtitle_enable_expr(t_start, t_end)}':format=auto{out_label}"
                )
                chains.append(vignette_chain)
            else:
                chains.append(
                    f"{prev}[{idx}:v]overlay=0:0:enable='{subtitle_enable_expr(t_start, t_end)}':format=auto{out_label}"
                )
            prev = out_label
            
        full_filter = kb_vf + ";" + ";".join(chains) + f";{prev}format=yuv420p[vout]"
        
        args.extend([
            "-t", f"{duration:.4f}",
            "-filter_complex", full_filter,
            "-map", "[vout]",
            "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-movflags", "+faststart",
            str(out_path)
        ])
    else:
        # Standard video only (no subtitles)
        vf_format = f"{vf},format=yuv420p"
        args.extend([
            "-t", f"{duration:.4f}",
            "-vf", vf_format,
            "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-movflags", "+faststart",
            str(out_path)
        ])

    ffmpeg(*args)


def concat_with_xfade(
    scene_clips: list[Path],
    durations: list[float],
    out_path: Path,
    closing_fade: bool = True,
) -> None:
    """
    Concatenate scene clips using FFmpeg xfade transition (crossfade) between each pair.
    """
    td = CROSSFADE_DURATION
    if len(scene_clips) == 1:
        if closing_fade:
            fade_st = max(0.0, durations[0] - CLOSING_FADE_DURATION)
            filter_complex = f"[0:v]fade=t=out:st={fade_st:.3f}:d={CLOSING_FADE_DURATION:.3f}[v_fadeout]"
            cmd = [
                "ffmpeg", "-y", "-i", str(scene_clips[0]),
                "-filter_complex", filter_complex,
                "-map", "[v_fadeout]", "-an",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                str(out_path),
            ]
        else:
            cmd = [
                "ffmpeg", "-y", "-i", str(scene_clips[0]),
                "-an",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                str(out_path),
            ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            tail = (result.stderr or result.stdout)[-4000:]
            raise FFmpegError(f"single clip concat failed:\n{tail}")
        return

    chains: list[str] = []
    cumulative_offset = 0.0

    for i in range(len(scene_clips) - 1):
        if i == 0:
            prev = "[0:v]"
        else:
            prev = f"[vx{i}]"

        cumulative_offset += durations[i]
        offset = max(0.0, cumulative_offset - td)
        out_label = f"[vx{i + 1}]"

        chains.append(
            f"{prev}[{i + 1}:v]xfade=transition=fade:duration={td:.3f}:offset={offset:.3f}{out_label}"
        )
        cumulative_offset -= td

    final_label = f"[vx{len(scene_clips) - 1}]"
    if closing_fade:
        total_duration = cumulative_offset + durations[-1]
        fade_st = max(0.0, total_duration - CLOSING_FADE_DURATION)
        chains.append(f"{final_label}fade=t=out:st={fade_st:.3f}:d={CLOSING_FADE_DURATION:.3f}[v_fadeout]")
        out_map = "[v_fadeout]"
    else:
        out_map = final_label
    filter_complex = ";".join(chains)

    cmd = (
        ["ffmpeg", "-y"]
        + [arg for clip in scene_clips for arg in ["-i", str(clip)]]
        + [
            "-filter_complex", filter_complex,
            "-map", out_map,
            "-an",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(out_path),
        ]
    )
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        tail = (result.stderr or result.stdout)[-4000:]
        raise FFmpegError(f"xfade concat failed:\n{tail}")


def main():
    parser = argparse.ArgumentParser(description="Render scene clips with Ken Burns + crossfades + subtitles")
    parser.add_argument("--project-dir", required=True, help="Path to the project directory")
    parser.add_argument("--force", action="store_true", help="Re-render even if clips already exist")
    parser.add_argument("--skip-subtitles", action="store_true", help="Skip subtitle overlay step")
    parser.add_argument("--subtitle-style", choices=["soft_halo", "classic_card"], default="soft_halo", help="Subtitle visual style (soft_halo or classic_card)")
    parser.add_argument("--no-motion", action="store_true", help="Disable Ken Burns zoom motion (removes all shaking/trembling)")
    parser.add_argument("--no-closing-fade", action="store_true", help="Disable 2s tail extension and closing fade out")
    args = parser.parse_args()

    if shutil.which("ffmpeg") is None:
        print("ERROR: ffmpeg not found in PATH.", file=sys.stderr)
        sys.exit(1)

    project_dir = Path(args.project_dir)
    scenes_path = project_dir / "scenes.json"
    session_path = project_dir / "session.json"
    timestamps_path = project_dir / "audio" / "timestamps.json"
    scenes_dir = project_dir / "temp" / "scenes"
    sub_dir = project_dir / "temp" / "subtitles"
    concat_path = project_dir / "temp" / "concat-video.mp4"
    out_path = project_dir / "temp" / "video-no-audio.mp4"

    for p in [scenes_path, session_path]:
        if not p.exists():
            print(f"ERROR: Required file not found: {p}", file=sys.stderr)
            sys.exit(1)

    scenes_data = json.loads(scenes_path.read_text(encoding="utf-8"))
    session = json.loads(session_path.read_text(encoding="utf-8"))

    aspect_ratio = session.get("visual", {}).get("aspect_ratio", "16:9")
    if aspect_ratio == "9:16":
        width, height = 1080, 1920
    else:
        width, height = RENDER_WIDTH, RENDER_HEIGHT
    fps = RENDER_FPS

    words = []
    if not args.skip_subtitles and timestamps_path.exists():
        words = json.loads(timestamps_path.read_text(encoding="utf-8")).get("words", [])

    scenes = scenes_data.get("scenes", [])
    scenes_dir.mkdir(parents=True, exist_ok=True)
    sub_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "temp").mkdir(parents=True, exist_ok=True)
    (project_dir / "output").mkdir(parents=True, exist_ok=True)

    font_path = detect_devanagari_font(project_dir)
    word_assignments = assign_words_to_scenes(words, scenes) if words else {}

    # ── Sub-stage A: Render each scene clip ──────────────────────────────────
    print(f"→ Rendering {len(scenes)} scene clips at {width}x{height} @ {fps}fps")
    scene_clips: list[Path] = []
    durations: list[float] = []

    prev_scene_ended_with_quote = False

    for idx, scene in enumerate(scenes):
        scene_id = scene["id"]
        start_t = float(scene.get("start_time") or 0.0)
        end_t = float(scene.get("end_time") or 0.0)
        duration = max(0.5, end_t - start_t)

        # For the last scene, extend duration by CLOSING_TAIL_EXTENSION (unless disabled)
        # so the final scene continues for post-narration reflection.
        is_last = (idx == len(scenes) - 1)
        if is_last:
            clip_duration = duration if args.no_closing_fade else (duration + CLOSING_TAIL_EXTENSION)
        else:
            clip_duration = duration + CROSSFADE_DURATION

        image_path = project_dir / scene["image_path"]
        clip_path = scenes_dir / f"{scene_id}.mp4"

        # Generate subtitle overlay frames
        subtitle_frames = []
        if words:
            subtitle_frames = generate_scene_subtitle_frames(
                scene, words, sub_dir, (width, height), font_path,
                clip_duration=clip_duration,
                prev_scene_ended_with_quote=prev_scene_ended_with_quote,
                style=args.subtitle_style,
                scene_words=word_assignments.get(idx, []),
            )

        if not image_path.exists():
            print(f"ERROR: Image not found: {image_path}", file=sys.stderr)
            sys.exit(1)

        is_quote = ">" in scene.get("text", "")
        prev_scene_ended_with_quote = is_quote

        if clip_path.exists() and not args.force:
            print(f"  ✓ Cached: {scene_id}.mp4 ({clip_duration:.2f}s)")
        else:
            print(f"  Rendering {scene_id}.mp4 ({clip_duration:.2f}s) with {len(subtitle_frames)} subtitle frames...")
            render_scene_clip(image_path, clip_duration, clip_path, width, height, fps, subtitle_frames, args.no_motion)

        scene_clips.append(clip_path)
        durations.append(clip_duration)

    # ── Sub-stage B: Concatenate with crossfade ───────────────────────────────
    print(f"→ Concatenating {len(scene_clips)} clips with {CROSSFADE_DURATION}s crossfade...")
    concat_with_xfade(scene_clips, durations, out_path, closing_fade=not args.no_closing_fade)
    print(f"  ✓ Concatenated video: {out_path}")
    print(f"✓ Video (no audio) ready: {out_path}")


if __name__ == "__main__":
    main()

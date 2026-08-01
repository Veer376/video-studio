"""
Stage 2 of render pipeline: Render scene clips with Ken Burns motion, concatenate with
crossfade transitions, and burn in ASS subtitles.

Sub-stages:
  A. Each image → temp/scenes/scene-NNN.mp4  (Ken Burns zoompan, silent)
  B. All scene clips → temp/concat-video.mp4  (xfade crossfade transitions)
  C. Burn ASS subtitles → temp/video-no-audio.mp4

Usage:
    python3 render_video.py --project-dir library/2026-08-01_krishna-motivation
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


CROSSFADE_DURATION = 0.4   # seconds of crossfade between scenes
KEN_BURNS_ZOOM     = 0.06  # max additional zoom (6%) applied over scene duration


class FFmpegError(RuntimeError):
    pass


def ffmpeg(*args: str) -> None:
    """Run an ffmpeg command, raise FFmpegError if it fails."""
    cmd = ["ffmpeg", "-y"] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        tail = (result.stderr or result.stdout)[-4000:]
        raise FFmpegError(f"ffmpeg failed:\n{tail}")


def detect_devanagari_fontsdir() -> str | None:
    """Return the directory containing a Devanagari-compatible font for libass fontsdir."""
    candidates = [
        "/System/Library/Fonts/Supplemental/Devanagari Sangam MN.ttc",
        "/System/Library/Fonts/Supplemental/ITFDevanagari.ttc",
        "/System/Library/Fonts/Supplemental/DevanagariMT.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
    ]
    for path_str in candidates:
        p = Path(path_str)
        if p.exists():
            return str(p.parent)
    return None


def render_scene_clip(
    image_path: Path,
    duration: float,
    out_path: Path,
    width: int,
    height: int,
    fps: int,
) -> None:
    """
    Render a single scene image as a silent MP4 clip with Ken Burns slow zoom.
    The image is scaled slightly larger, then zoompan slowly zooms in over the clip duration.
    """
    frames = max(1, round(duration * fps))
    # Zoom step: go from 1.0 to 1.0+KEN_BURNS_ZOOM linearly over all frames
    step = KEN_BURNS_ZOOM / max(1, frames - 1)

    # Scale slightly larger than target to provide headroom for zoom + pan
    overscan_w = width + 160
    overscan_h = height + 160

    zoom_expr = f"1.0+on*{step:.8f}"
    x_expr = "(iw-iw/zoom)/2"
    y_expr = "(ih-ih/zoom)/2"

    vf = (
        f"scale={overscan_w}:{overscan_h}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},"
        f"zoompan=z='{zoom_expr}':x='{x_expr}':y='{y_expr}':d={frames}:s={width}x{height}:fps={fps},"
        f"format=yuv420p"
    )

    ffmpeg(
        "-loop", "1",
        "-i", str(image_path),
        "-t", f"{duration:.4f}",
        "-vf", vf,
        "-an",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
        "-movflags", "+faststart",
        str(out_path),
    )


def concat_with_xfade(scene_clips: list[Path], durations: list[float], out_path: Path) -> None:
    """
    Concatenate scene clips using FFmpeg xfade transition (crossfade) between each pair.
    The offset for each xfade is the cumulative duration of all previous clips minus
    accumulated transition overlap.
    """
    if len(scene_clips) == 1:
        # No crossfade needed for single scene
        ffmpeg("-i", str(scene_clips[0]), "-c", "copy", str(out_path))
        return

    td = CROSSFADE_DURATION
    args = ["-y"]
    for clip in scene_clips:
        args += ["-i", str(clip)]

    # Build xfade filter chain
    chains: list[str] = []
    cumulative_offset = 0.0

    for i in range(len(scene_clips) - 1):
        in_label = f"[v{i}]" if i > 0 else f"[{0}:v]"
        # First iteration: inputs are [0:v][1:v]
        # Subsequent: accumulated label + next input
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
        cumulative_offset -= td  # account for overlap

    final_label = f"[vx{len(scene_clips) - 1}]"
    filter_complex = ";".join(chains)

    cmd = (
        ["ffmpeg", "-y"]
        + [arg for clip in scene_clips for arg in ["-i", str(clip)]]
        + [
            "-filter_complex", filter_complex,
            "-map", final_label,
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


def burn_subtitles(video_path: Path, ass_path: Path, out_path: Path, fontsdir: str | None) -> None:
    """
    Burn ASS subtitles into the video using FFmpeg's ass filter.
    Falls back to writing video without subtitles if the ass filter fails.
    """
    # Build the ass filter — specify fontsdir if we know where the Devanagari font lives
    if fontsdir:
        ass_filter = f"ass={str(ass_path).replace(':', '\\:').replace('\\', '/')}:fontsdir={fontsdir}"
    else:
        ass_filter = f"ass={str(ass_path).replace(':', '\\:').replace('\\', '/')}"

    try:
        ffmpeg(
            "-i", str(video_path),
            "-vf", ass_filter,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(out_path),
        )
        print("✓ ASS subtitles burned into video")
    except FFmpegError as e:
        print(f"  ⚠ Subtitle burning failed ({str(e)[:120]}). Copying video without subtitles.", file=sys.stderr)
        # Fallback: copy video without subtitles
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(video_path), "-c", "copy", str(out_path)],
            capture_output=True, check=True,
        )


def main():
    parser = argparse.ArgumentParser(description="Render scene clips with Ken Burns + crossfades + subtitles")
    parser.add_argument("--project-dir", required=True, help="Path to the project directory")
    parser.add_argument("--force", action="store_true", help="Re-render even if clips already exist")
    parser.add_argument("--skip-subtitles", action="store_true", help="Skip subtitle burning step")
    args = parser.parse_args()

    if shutil.which("ffmpeg") is None:
        print("ERROR: ffmpeg not found in PATH. Install ffmpeg first.", file=sys.stderr)
        sys.exit(1)

    project_dir = Path(args.project_dir)
    scenes_path = project_dir / "scenes.json"
    session_path = project_dir / "session.json"
    ass_path = project_dir / "subtitles" / "story.ass"
    scenes_dir = project_dir / "temp" / "scenes"
    concat_path = project_dir / "temp" / "concat-video.mp4"
    out_path = project_dir / "temp" / "video-no-audio.mp4"

    for p in [scenes_path, session_path]:
        if not p.exists():
            print(f"ERROR: Required file not found: {p}", file=sys.stderr)
            sys.exit(1)

    scenes_data = json.loads(scenes_path.read_text(encoding="utf-8"))
    session = json.loads(session_path.read_text(encoding="utf-8"))

    aspect_ratio = session.get("video", {}).get("aspect_ratio", "16:9")
    fps = int(session.get("video", {}).get("fps", 30))
    if aspect_ratio == "9:16":
        width, height = 576, 1024
    elif aspect_ratio == "1:1":
        width, height = 768, 768
    else:
        width, height = 1024, 576

    scenes = scenes_data.get("scenes", [])
    scenes_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "temp").mkdir(parents=True, exist_ok=True)
    (project_dir / "output").mkdir(parents=True, exist_ok=True)

    # ── Sub-stage A: Render each scene clip ──────────────────────────────────
    print(f"→ Rendering {len(scenes)} scene clips at {width}x{height} @ {fps}fps")
    scene_clips: list[Path] = []
    durations: list[float] = []

    for scene in scenes:
        scene_id = scene["id"]
        start_t = float(scene.get("start_time") or 0.0)
        end_t = float(scene.get("end_time") or 0.0)
        duration = max(0.5, end_t - start_t)   # enforce minimum 0.5s

        image_path = project_dir / scene["image_path"]
        clip_path = scenes_dir / f"{scene_id}.mp4"

        if not image_path.exists():
            print(f"ERROR: Image not found: {image_path}", file=sys.stderr)
            sys.exit(1)

        if clip_path.exists() and not args.force:
            print(f"  ✓ Cached: {scene_id}.mp4 ({duration:.2f}s)")
        else:
            print(f"  Rendering {scene_id}.mp4 ({duration:.2f}s)...")
            render_scene_clip(image_path, duration, clip_path, width, height, fps)

        scene_clips.append(clip_path)
        durations.append(duration)

    # ── Sub-stage B: Concatenate with crossfade ───────────────────────────────
    print(f"→ Concatenating {len(scene_clips)} clips with {CROSSFADE_DURATION}s crossfade...")
    concat_with_xfade(scene_clips, durations, concat_path)
    print(f"  ✓ Concatenated video: {concat_path}")

    # ── Sub-stage C: Burn subtitles ───────────────────────────────────────────
    if args.skip_subtitles or not ass_path.exists():
        print("  Skipping subtitle burning (no .ass file found or --skip-subtitles set)")
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(concat_path), "-c", "copy", str(out_path)],
            capture_output=True, check=True,
        )
    else:
        print(f"→ Burning subtitles from {ass_path.name}...")
        fontsdir = detect_devanagari_fontsdir()
        burn_subtitles(concat_path, ass_path, out_path, fontsdir)

    print(f"✓ Video (no audio) ready: {out_path}")


if __name__ == "__main__":
    main()

"""
Stage 2 of render pipeline: Render scene clips with Ken Burns motion, burn in word-by-word
Pillow-rendered subtitle overlays, and concatenate them with crossfade transitions.

This implementation uses transparent PNGs rendered via Pillow and overlays them onto the clips
using FFmpeg's overlay filter, bypassing the need for FFmpeg's libass library.

Usage:
    python3 render_video.py --project-dir library/2026-08-01_krishna-motivation
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

# Add project src to path for imports
project_root = Path(__file__).resolve().parents[4]
sys.path.append(str(project_root / "src"))
from subtitles import write_subtitle_overlay
from renderer import detect_devanagari_font


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


def generate_scene_subtitle_frames(
    scene: dict,
    words: list[dict],
    out_dir: Path,
    size: tuple[int, int],
    font_path: Path | None,
) -> list[tuple[Path, float, float]]:
    """
    Generate transparent PNG overlays for each word in the scene using Pillow.
    Timings are calculated relative to the scene's start time (0.0s).
    """
    start_t = scene["start_time"]
    end_t = scene["end_time"]
    scene_id = scene["id"]

    # Filter words belonging to this scene's time window
    scene_words = [
        w for w in words
        if w["start"] >= (start_t - 0.15) and w["start"] < end_t
    ]
    if not scene_words:
        return []

    # Build the full text for this scene to lock the layout wrapping structure
    full_text = " ".join(w["word"] for w in scene_words)

    frames = []
    cumulative = []

    for i, word in enumerate(scene_words):
        cumulative.append(word["word"].strip())
        visible_text = " ".join(cumulative)

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
        )
        frames.append((png_path, t_start, t_end))

    return frames


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
        # Zoompan motion (Ken Burns zoom-in) rendered at 3x resolution to completely eliminate jitter/shaking
        frames = max(1, round(duration * fps))
        step = KEN_BURNS_ZOOM / max(1, frames - 1)

        hires_w = width * 3
        hires_h = height * 3

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
        # Extend inputs for each subtitle frame PNG
        for png_path, _, _ in subtitle_frames:
            args.extend(["-loop", "1", "-i", str(png_path)])

        chains: list[str] = []
        prev = "[kbv]"
        kb_vf = f"{vf}[kbv]"
        
        for idx, (_, t_start, t_end) in enumerate(subtitle_frames, start=1):
            out_label = f"[ov{idx}]"
            chains.append(
                f"{prev}[{idx}:v]overlay=0:0:enable='between(t,{t_start:.4f},{t_end:.4f})':format=auto{out_label}"
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


def concat_with_xfade(scene_clips: list[Path], durations: list[float], out_path: Path) -> None:
    """
    Concatenate scene clips using FFmpeg xfade transition (crossfade) between each pair.
    """
    if len(scene_clips) == 1:
        ffmpeg("-i", str(scene_clips[0]), "-c", "copy", str(out_path))
        return

    td = CROSSFADE_DURATION
    args = ["-y"]
    for clip in scene_clips:
        args += ["-i", str(clip)]

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


def main():
    parser = argparse.ArgumentParser(description="Render scene clips with Ken Burns + crossfades + subtitles")
    parser.add_argument("--project-dir", required=True, help="Path to the project directory")
    parser.add_argument("--force", action="store_true", help="Re-render even if clips already exist")
    parser.add_argument("--skip-subtitles", action="store_true", help="Skip subtitle overlay step")
    parser.add_argument("--no-motion", action="store_true", help="Disable Ken Burns zoom motion (removes all shaking/trembling)")
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

    aspect_ratio = session.get("video", {}).get("aspect_ratio", "16:9")
    fps = int(session.get("video", {}).get("fps", 30))
    if aspect_ratio == "9:16":
        width, height = 576, 1024
    elif aspect_ratio == "1:1":
        width, height = 768, 768
    else:
        width, height = 1024, 576

    words = []
    if not args.skip_subtitles and timestamps_path.exists():
        words = json.loads(timestamps_path.read_text(encoding="utf-8")).get("words", [])

    scenes = scenes_data.get("scenes", [])
    scenes_dir.mkdir(parents=True, exist_ok=True)
    sub_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "temp").mkdir(parents=True, exist_ok=True)
    (project_dir / "output").mkdir(parents=True, exist_ok=True)

    font_path = detect_devanagari_font(project_dir)

    # ── Sub-stage A: Render each scene clip ──────────────────────────────────
    print(f"→ Rendering {len(scenes)} scene clips at {width}x{height} @ {fps}fps")
    scene_clips: list[Path] = []
    durations: list[float] = []

    for idx, scene in enumerate(scenes):
        scene_id = scene["id"]
        start_t = float(scene.get("start_time") or 0.0)
        end_t = float(scene.get("end_time") or 0.0)
        duration = max(0.5, end_t - start_t)

        # Pad clip duration with CROSSFADE_DURATION (except for the last scene)
        # so the crossfade overlap doesn't shrink the active scene duration.
        is_last = (idx == len(scenes) - 1)
        clip_duration = duration if is_last else (duration + CROSSFADE_DURATION)

        image_path = project_dir / scene["image_path"]
        clip_path = scenes_dir / f"{scene_id}.mp4"

        # Generate subtitle overlay frames
        subtitle_frames = []
        if words:
            subtitle_frames = generate_scene_subtitle_frames(
                scene, words, sub_dir, (width, height), font_path
            )

        if not image_path.exists():
            print(f"ERROR: Image not found: {image_path}", file=sys.stderr)
            sys.exit(1)

        if clip_path.exists() and not args.force:
            print(f"  ✓ Cached: {scene_id}.mp4 ({clip_duration:.2f}s)")
        else:
            print(f"  Rendering {scene_id}.mp4 ({clip_duration:.2f}s) with {len(subtitle_frames)} subtitle frames...")
            render_scene_clip(image_path, clip_duration, clip_path, width, height, fps, subtitle_frames, args.no_motion)

        scene_clips.append(clip_path)
        durations.append(clip_duration)

    # ── Sub-stage B: Concatenate with crossfade ───────────────────────────────
    print(f"→ Concatenating {len(scene_clips)} clips with {CROSSFADE_DURATION}s crossfade...")
    concat_with_xfade(scene_clips, durations, out_path)
    print(f"  ✓ Concatenated video: {out_path}")
    print(f"✓ Video (no audio) ready: {out_path}")


if __name__ == "__main__":
    main()

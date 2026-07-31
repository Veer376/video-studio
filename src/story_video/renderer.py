from __future__ import annotations

import platform
from pathlib import Path

from . import ffmpeg
from .images import validate_image
from .models import Manifest, Scene
from .subtitles import write_srt, write_subtitle_overlay


def prepare_dirs(base_dir: Path) -> None:
    for rel in [
        "generated/images",
        "generated/audio",
        "generated/subtitles",
        "generated/scenes",
        "generated/temp",
        "output",
        "assets/music",
        "assets/fonts",
        "assets/references",
    ]:
        (base_dir / rel).mkdir(parents=True, exist_ok=True)


def render_video(manifest: Manifest, base_dir: Path, force: bool = False) -> Path:
    ffmpeg.require_tools()
    prepare_dirs(base_dir)
    width, height = manifest.project.width_height
    if manifest.subtitles_enabled:
        write_srt(manifest, base_dir / "generated/subtitles/story.srt")

    scene_paths: list[Path] = []
    visual_durations: list[float] = []
    for index, scene in enumerate(manifest.scenes):
        transition = scene.transition.duration_seconds if index < len(manifest.scenes) - 1 else 0.0
        visual_duration = float(scene.duration_seconds or 0) + transition
        visual_durations.append(visual_duration)
        scene_paths.append(
            render_scene(
                scene,
                base_dir,
                width,
                height,
                manifest.project.fps,
                visual_duration,
                subtitles_enabled=manifest.subtitles_enabled,
                force=force,
            )
        )

    concat_video = base_dir / "generated/temp/concat-video.mp4"
    concat_scenes(scene_paths, visual_durations, [scene.transition.duration_seconds for scene in manifest.scenes[:-1]], concat_video)

    audio_path = base_dir / "generated/temp/narration.wav"
    concat_audio(manifest, base_dir, audio_path)

    output_path = base_dir / "output/final-video.mp4"
    mux_audio(concat_video, audio_path, output_path, manifest.background_music_path, base_dir)
    if not ffmpeg.video_has_stream(output_path):
        raise RuntimeError(f"Rendered MP4 is not probeable: {output_path}")
    return output_path


def render_scene(
    scene: Scene,
    base_dir: Path,
    width: int,
    height: int,
    fps: int,
    visual_duration: float,
    subtitles_enabled: bool = False,
    force: bool = False,
) -> Path:
    if not scene.image_path or not scene.audio_path or not scene.duration_seconds:
        raise ValueError(f"{scene.id}: scene requires image_path, audio_path, and duration_seconds")
    image_path = base_dir / scene.image_path
    validate_image(image_path)
    out_path = base_dir / f"generated/scenes/{scene.id}.mp4"
    if out_path.exists() and not force:
        return out_path

    frames = max(1, round(float(visual_duration) * fps))
    zoom_expr, x_expr, y_expr = motion_filter(scene.motion.type, scene.motion.intensity, frames)
    vf = (
        f"scale={width + 160}:{height + 160}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},"
        f"zoompan=z='{zoom_expr}':x='{x_expr}':y='{y_expr}':d={frames}:s={width}x{height}:fps={fps}"
    )
    args = ["ffmpeg", "-y", "-loop", "1", "-i", str(image_path)]
    if subtitles_enabled:
        overlay_path = base_dir / f"generated/subtitles/{scene.id}-overlay.png"
        write_subtitle_overlay(scene.subtitle or scene.narration, overlay_path, (width, height), detect_devanagari_font(base_dir))
        vf = f"{vf}[v0];[v0][1:v]overlay=0:0:format=auto,format=yuv420p[v]"
        args.extend(["-loop", "1", "-i", str(overlay_path)])
        filter_flag = "-filter_complex"
        map_args = ["-map", "[v]"]
    else:
        vf = f"{vf},format=yuv420p"
        filter_flag = "-vf"
        map_args = []
    args.extend(
        [
            "-t",
            f"{visual_duration:.3f}",
            filter_flag,
            vf,
            *map_args,
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "18",
            "-movflags",
            "+faststart",
            str(out_path),
        ]
    )
    ffmpeg.run(args)
    return out_path


def motion_filter(motion_type: str, intensity: float, frames: int) -> tuple[str, str, str]:
    end_zoom = 1.0 + max(0.0, min(float(intensity), 0.12))
    step = (end_zoom - 1.0) / max(1, frames - 1)
    if motion_type == "slow_zoom_out":
        return f"{end_zoom:.6f}-on*{step:.8f}", "(iw-iw/zoom)/2", "(ih-ih/zoom)/2"
    if motion_type == "slow_pan_right":
        return f"1.0+on*{step / 2:.8f}", f"(iw-iw/zoom)*on/{frames}", "(ih-ih/zoom)/2"
    return f"1.0+on*{step:.8f}", "(iw-iw/zoom)/2", "(ih-ih/zoom)/2"


def concat_scenes(scene_paths: list[Path], durations: list[float], transitions: list[float], out_path: Path) -> None:
    if len(scene_paths) == 1:
        ffmpeg.run(["ffmpeg", "-y", "-i", str(scene_paths[0]), "-c", "copy", str(out_path)])
        return
    args = ["ffmpeg", "-y"]
    for path in scene_paths:
        args.extend(["-i", str(path)])
    chains: list[str] = []
    previous = "[0:v]"
    elapsed = durations[0]
    for index, transition in enumerate(transitions, start=1):
        out_label = f"[vx{index}]"
        offset = max(0.0, elapsed - transition)
        chains.append(f"{previous}[{index}:v]xfade=transition=fade:duration={transition:.3f}:offset={offset:.3f}{out_label}")
        previous = out_label
        elapsed += durations[index] - transition
    args.extend(["-filter_complex", ";".join(chains), "-map", previous, "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out_path)])
    ffmpeg.run(args)


def concat_audio(manifest: Manifest, base_dir: Path, out_path: Path) -> None:
    list_path = out_path.with_suffix(".txt")
    audio_paths = [base_dir / scene.audio_path for scene in manifest.scenes if scene.audio_path]
    list_path.write_text("".join(f"file '{path.resolve()}'\n" for path in audio_paths), encoding="utf-8")
    ffmpeg.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_path), "-c:a", "pcm_s16le", str(out_path)])


def mux_audio(video_path: Path, audio_path: Path, out_path: Path, music_path: str | None, base_dir: Path) -> None:
    args = ["ffmpeg", "-y", "-i", str(video_path), "-i", str(audio_path)]
    filter_complex = None
    audio_map = "1:a"
    if music_path:
        resolved_music = base_dir / music_path
        args.extend(["-i", str(resolved_music)])
        filter_complex = "[1:a]volume=1.0[a0];[2:a]volume=0.12,afade=t=in:st=0:d=1.5[a1];[a0][a1]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        audio_map = "[aout]"
    if filter_complex:
        args.extend(["-filter_complex", filter_complex])
    args.extend(["-map", "0:v", "-map", audio_map, "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out_path)])
    ffmpeg.run(args)


def detect_devanagari_font(base_dir: Path) -> Path | None:
    candidates = [
        base_dir / "assets/fonts/Devanagari.ttf",
        Path("/System/Library/Fonts/Supplemental/Devanagari Sangam MN.ttc"),
        Path("/System/Library/Fonts/Supplemental/ITFDevanagari.ttc"),
        Path("/System/Library/Fonts/Supplemental/DevanagariMT.ttc"),
    ]
    return next((path for path in candidates if path.exists()), None)


def escape_filter_path(path: Path) -> str:
    raw = str(path.resolve())
    if platform.system() == "Windows":
        raw = raw.replace("\\", "\\\\").replace(":", "\\:")
    return raw.replace("'", "\\'")

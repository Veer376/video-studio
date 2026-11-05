#!/usr/bin/env python3
"""Render a KathaMind mixed-media video with subtitles and narration only.

This renderer is intentionally conservative. It does NOT add background music,
jitter, grain, punch-zooms, or global scene transitions. Those can be layered
later without touching transcription/alignment.

Pipeline:

    production-manifest.json + scenes.json + audio/timestamps.json
                         |
                         v
        temp/render-kathamind/scenes-clean/*.mp4
                         |
                         v
               temp/visual-master.mp4
                         |
            existing subtitle timing/layout logic
                         |
                         v
        temp/render-kathamind/scenes-captioned/*.mp4
                         |
                         v
              temp/captioned-master.mp4
                         |
                    narration.mp3
                         |
                         v
              output/final-video-no-bgm.mp4

Design decisions for this first production render:

* production-manifest.json is the media source of truth.
* A completed generated scene video supersedes that scene's stills.
* Still continuations run primary -> c01 -> c02 during the spoken interval.
* The terminal frame holds through narration pauses until the next scene begins.
* Continuation frames use a short in-scene dissolve; semantic scene changes are
  hard cuts.
* Existing word-to-scene assignment and subtitle image generation are reused.
* Final video contains narration only. BGM can be added later while stream-copying
  the video track, so subtitles do not need to be rebuilt.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


DEFAULT_WIDTH = 1920
DEFAULT_HEIGHT = 1080
DEFAULT_FPS = 24
DEFAULT_CRF = 18
DEFAULT_PRESET = "veryfast"
DEFAULT_CONTINUATION_FADE = 0.22
DEFAULT_SUBTITLE_MODE = "phrase"
DEFAULT_SUBTITLE_STYLE = "classic_card"
DEFAULT_SUBTITLE_MAX_WORDS = 6
DEFAULT_SUBTITLE_MAX_SECONDS = 2.35
DEFAULT_SUBTITLE_PAUSE_SPLIT = 0.34
RENDER_NAMESPACE = "render-kathamind"


class RenderError(RuntimeError):
    pass


@dataclass(frozen=True)
class SceneSlot:
    scene_index: int
    scene_id: str
    slot_start: float
    spoken_end: float
    slot_end: float
    is_last: bool = False

    @property
    def spoken_duration(self) -> float:
        return max(0.0, self.spoken_end - self.slot_start)

    @property
    def pause_duration(self) -> float:
        return max(0.0, self.slot_end - self.spoken_end)

    @property
    def slot_duration(self) -> float:
        return max(0.0, self.slot_end - self.slot_start)

    def frame_start(self, fps: int) -> int:
        return round(self.slot_start * fps)

    def frame_spoken_end(self, fps: int) -> int:
        start = self.frame_start(fps)
        end = self.frame_end(fps)
        return min(end, max(start, round(self.spoken_end * fps)))

    def frame_end(self, fps: int) -> int:
        # Only the terminal boundary rounds upward. This guarantees the visual
        # master is never shorter than narration, while every internal boundary
        # is shared by adjacent scenes and therefore cannot accumulate drift.
        if self.is_last:
            return math.ceil(self.slot_end * fps)
        return round(self.slot_end * fps)

    def render_spoken_duration(self, fps: int) -> float:
        return (self.frame_spoken_end(fps) - self.frame_start(fps)) / fps

    def render_slot_duration(self, fps: int) -> float:
        return (self.frame_end(fps) - self.frame_start(fps)) / fps

    def render_pause_duration(self, fps: int) -> float:
        return (self.frame_end(fps) - self.frame_spoken_end(fps)) / fps


@dataclass(frozen=True)
class SceneMedia:
    scene_id: str
    kind: str  # "video" or "images"
    paths: tuple[Path, ...]


@dataclass(frozen=True)
class PhraseCaption:
    text: str
    relative_start: float
    relative_end: float
    word_count: int


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RenderError(f"Required file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RenderError(f"Invalid JSON: {path}: {exc}") from exc


def _run(cmd: Sequence[str], *, label: str) -> None:
    result = subprocess.run(list(cmd), capture_output=True, text=True)
    if result.returncode != 0:
        tail = (result.stderr or result.stdout)[-6000:]
        raise RenderError(f"{label} failed:\n{tail}")


def _probe_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nw=1:nk=1",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RenderError(f"ffprobe failed for {path}: {(result.stderr or result.stdout)[-2000:]}")
    try:
        return float(result.stdout.strip())
    except ValueError as exc:
        raise RenderError(f"Could not read duration for {path}") from exc


def _assert_tooling() -> None:
    missing = [name for name in ("ffmpeg", "ffprobe") if shutil.which(name) is None]
    if missing:
        raise RenderError(f"Missing required tool(s): {', '.join(missing)}")


def _ensure_macos_font_runtime() -> None:
    """Mirror the current renderer's macOS libraqm bootstrap before Pillow import.

    The existing subtitle renderer deliberately re-execs with Homebrew's lib path
    so Devanagari shaping can load correctly. Keep that behavior for render mode,
    but do not trigger it merely by importing this module in tests.
    """

    if sys.platform != "darwin":
        return
    homebrew_lib = "/opt/homebrew/lib"
    current = os.environ.get("DYLD_LIBRARY_PATH", "")
    if homebrew_lib in current.split(":"):
        return
    os.environ["DYLD_LIBRARY_PATH"] = homebrew_lib + (":" + current if current else "")
    os.execv(sys.executable, [sys.executable] + sys.argv)


def build_scene_slots(scenes: list[dict], narration_duration: float) -> list[SceneSlot]:
    if not scenes:
        raise RenderError("scenes.json contains no scenes")
    if narration_duration <= 0:
        raise RenderError("Narration duration must be positive")

    slots: list[SceneSlot] = []
    previous_start = -math.inf
    for idx, scene in enumerate(scenes):
        scene_id = str(scene.get("id") or "")
        if not scene_id:
            raise RenderError(f"Scene at index {idx} has no id")
        try:
            start = float(scene["start_time"])
            spoken_end = float(scene["end_time"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RenderError(f"{scene_id} has invalid start_time/end_time") from exc

        if start < previous_start:
            raise RenderError("Scenes are not ordered by start_time")
        if spoken_end < start:
            raise RenderError(f"{scene_id} ends before it starts")

        if idx + 1 < len(scenes):
            try:
                slot_end = float(scenes[idx + 1]["start_time"])
            except (KeyError, TypeError, ValueError) as exc:
                raise RenderError(f"Scene after {scene_id} has invalid start_time") from exc
        else:
            slot_end = narration_duration

        if slot_end + 1e-6 < spoken_end:
            raise RenderError(
                f"{scene_id} spoken interval overlaps the next scene: "
                f"spoken_end={spoken_end:.3f}, slot_end={slot_end:.3f}"
            )
        if slot_end <= start:
            raise RenderError(f"{scene_id} has non-positive visual slot")

        slots.append(SceneSlot(idx, scene_id, start, spoken_end, slot_end, idx == len(scenes) - 1))
        previous_start = start

    if abs(slots[0].slot_start) > 1e-3:
        raise RenderError(f"First scene must start at 0; got {slots[0].slot_start:.3f}")
    if abs(slots[-1].slot_end - narration_duration) > 1e-3:
        raise RenderError("Last scene does not terminate at narration duration")
    return slots


def validate_word_ownership(scenes: list[dict], words: list[dict]) -> dict[int, list[dict]]:
    """Use authored inclusive word indices and verify legacy time assignment agrees.

    This preserves the hard-won subtitle alignment work. For this production,
    scenes.json partitions 0..N-1 exactly using inclusive word_start/word_end.
    We fail loudly if that invariant changes.
    """

    from studio.subtitles.subtitles import assign_words_to_scenes

    if not words:
        raise RenderError("timestamps.json contains no words")

    indexed: dict[int, list[dict]] = {}
    expected_start = 0
    for idx, scene in enumerate(scenes):
        scene_id = scene.get("id", f"scene-index-{idx}")
        try:
            start = int(scene["word_start"])
            end = int(scene["word_end"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RenderError(f"{scene_id} is missing valid word_start/word_end") from exc
        if start != expected_start:
            raise RenderError(
                f"Word ownership is not contiguous at {scene_id}: expected {expected_start}, got {start}"
            )
        if end < start or end >= len(words):
            raise RenderError(f"Invalid word range for {scene_id}: {start}..{end}")
        indexed[idx] = words[start : end + 1]
        expected_start = end + 1

    if expected_start != len(words):
        raise RenderError(
            f"Scene word ranges cover {expected_start} words but timestamps contain {len(words)}"
        )

    legacy = assign_words_to_scenes(words, scenes)
    for idx, scene_words in indexed.items():
        legacy_words = legacy.get(idx, [])
        if len(scene_words) != len(legacy_words):
            raise RenderError(
                f"Subtitle assignment disagreement in {scenes[idx]['id']}: "
                f"index={len(scene_words)} vs time={len(legacy_words)}"
            )
        for a, b in zip(scene_words, legacy_words):
            if abs(float(a["start"]) - float(b["start"])) > 1e-6:
                raise RenderError(f"Subtitle timestamp ownership disagreement in {scenes[idx]['id']}")
    return indexed


def _continuation_sort_key(asset_id: str) -> tuple[int, str]:
    match = re.search(r":c(\d+)$", asset_id)
    return (int(match.group(1)) if match else 10_000, asset_id)


def resolve_scene_media(project_dir: Path, manifest_assets: dict, scene_id: str) -> SceneMedia:
    video_id = f"{scene_id}:video"
    video = manifest_assets.get(video_id)
    if isinstance(video, dict) and video.get("status") == "complete":
        rel = video.get("output_path")
        if not rel:
            raise RenderError(f"{video_id} is complete but has no output_path")
        path = project_dir / rel
        if not path.is_file():
            raise RenderError(f"Manifest output missing: {path}")
        return SceneMedia(scene_id, "video", (path,))

    primary_id = f"{scene_id}:primary"
    primary = manifest_assets.get(primary_id)
    if not isinstance(primary, dict) or primary.get("status") != "complete":
        raise RenderError(f"Missing complete primary visual for {scene_id}")

    asset_ids = [primary_id]
    asset_ids.extend(
        sorted(
            [
                aid
                for aid, record in manifest_assets.items()
                if aid.startswith(f"{scene_id}:c")
                and isinstance(record, dict)
                and record.get("status") == "complete"
            ],
            key=_continuation_sort_key,
        )
    )

    paths: list[Path] = []
    for asset_id in asset_ids:
        record = manifest_assets[asset_id]
        rel = record.get("output_path")
        if not rel:
            raise RenderError(f"{asset_id} is complete but has no output_path")
        path = project_dir / rel
        if not path.is_file():
            raise RenderError(f"Manifest output missing: {path}")
        paths.append(path)
    return SceneMedia(scene_id, "images", tuple(paths))


def resolve_all_media(project_dir: Path, scenes: list[dict], manifest_assets: dict) -> list[SceneMedia]:
    return [resolve_scene_media(project_dir, manifest_assets, scene["id"]) for scene in scenes]


def build_phrase_captions(
    scene_words: Sequence[dict],
    *,
    scene_start: float,
    scene_end: float,
    max_words: int = DEFAULT_SUBTITLE_MAX_WORDS,
    max_seconds: float = DEFAULT_SUBTITLE_MAX_SECONDS,
    pause_split: float = DEFAULT_SUBTITLE_PAUSE_SPLIT,
) -> list[PhraseCaption]:
    """Group already-aligned words into stable, readable subtitle phrases.

    This is presentation only; it does not perform transcription or alignment.
    Word ownership/timestamps remain exactly those produced by the existing
    alignment pipeline. The legacy cumulative word-reveal mode remains available
    through --subtitle-mode legacy-word.
    """

    from studio.subtitles.subtitles import format_word_for_display

    if not scene_words:
        return []
    if max_words < 1 or max_seconds <= 0 or pause_split < 0:
        raise RenderError("Invalid phrase subtitle settings")

    groups: list[list[dict]] = []
    current: list[dict] = []

    for idx, word in enumerate(scene_words):
        current.append(word)
        next_word = scene_words[idx + 1] if idx + 1 < len(scene_words) else None
        spoken_span = float(current[-1]["end"]) - float(current[0]["start"])
        clean = str(word.get("word") or "").strip()
        sentence_end = bool(re.search(r"[।.!?…][\"'’”)]*$", clean))
        next_gap = (
            float(next_word["start"]) - float(word["end"])
            if next_word is not None
            else max(0.0, scene_end - float(word["end"]))
        )
        should_flush = (
            len(current) >= max_words
            or sentence_end
            or next_gap >= pause_split
            or (spoken_span >= max_seconds and len(current) >= 3)
            or next_word is None
        )
        if should_flush:
            groups.append(current)
            current = []

    captions: list[PhraseCaption] = []
    for idx, group in enumerate(groups):
        start_abs = float(group[0]["start"])
        last_end_abs = float(group[-1]["end"])
        if idx + 1 < len(groups):
            next_start_abs = float(groups[idx + 1][0]["start"])
        else:
            next_start_abs = scene_end

        # Keep a phrase on screen until the next phrase for ordinary cadence,
        # but let a genuinely long pause breathe with no subtitle.
        gap = max(0.0, next_start_abs - last_end_abs)
        end_abs = next_start_abs if gap < pause_split else min(next_start_abs, last_end_abs + 0.22)
        if end_abs <= start_abs + 0.08:
            end_abs = min(scene_end, start_abs + 0.08)

        text = " ".join(
            format_word_for_display(str(item.get("word") or "").replace(">", "").strip())
            for item in group
            if str(item.get("word") or "").strip()
        ).strip()
        if text and end_abs > start_abs:
            captions.append(
                PhraseCaption(
                    text=text,
                    relative_start=max(0.0, start_abs - scene_start),
                    relative_end=max(0.0, end_abs - scene_start),
                    word_count=len(group),
                )
            )
    return captions


def _normalize_filter(width: int, height: int, fps: int) -> str:
    return (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},setsar=1,fps={fps},format=yuv420p"
    )


def _encode_args(fps: int, crf: int, preset: str) -> list[str]:
    return [
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        preset,
        "-crf",
        str(crf),
        "-pix_fmt",
        "yuv420p",
        "-r",
        str(fps),
        "-movflags",
        "+faststart",
    ]


def render_video_scene(
    source: Path,
    slot: SceneSlot,
    output: Path,
    *,
    width: int,
    height: int,
    fps: int,
    crf: int,
    preset: str,
) -> None:
    source_duration = _probe_duration(source)
    render_spoken = slot.render_spoken_duration(fps)
    render_slot = slot.render_slot_duration(fps)
    action_duration = min(render_spoken, source_duration)
    if action_duration <= 0:
        raise RenderError(f"Generated video has no usable duration: {source}")
    freeze_duration = max(0.0, render_slot - action_duration)
    vf = (
        f"{_normalize_filter(width, height, fps)},"
        f"trim=duration={action_duration:.6f},setpts=PTS-STARTPTS,"
        f"tpad=stop_mode=clone:stop_duration={freeze_duration:.6f},"
        f"trim=duration={render_slot:.6f},setpts=PTS-STARTPTS"
    )
    cmd = ["ffmpeg", "-y", "-i", str(source), "-vf", vf, "-t", f"{render_slot:.6f}"]
    cmd += _encode_args(fps, crf, preset)
    cmd.append(str(output))
    _run(cmd, label=f"Render generated video scene {slot.scene_id}")


def render_image_scene(
    sources: Sequence[Path],
    slot: SceneSlot,
    output: Path,
    *,
    width: int,
    height: int,
    fps: int,
    crf: int,
    preset: str,
    continuation_fade: float,
) -> None:
    if not sources:
        raise RenderError(f"No image sources for {slot.scene_id}")
    spoken = slot.render_spoken_duration(fps)
    pause = slot.render_pause_duration(fps)
    render_slot = slot.render_slot_duration(fps)
    if spoken <= 0:
        raise RenderError(f"{slot.scene_id} has no spoken interval")

    if len(sources) == 1:
        vf = f"{_normalize_filter(width, height, fps)},trim=duration={render_slot:.6f},setpts=PTS-STARTPTS"
        cmd = [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-framerate",
            str(fps),
            "-i",
            str(sources[0]),
            "-vf",
            vf,
            "-t",
            f"{render_slot:.6f}",
        ]
        cmd += _encode_args(fps, crf, preset)
        cmd.append(str(output))
        _run(cmd, label=f"Render still scene {slot.scene_id}")
        return

    transition = min(
        max(0.0, continuation_fade),
        max(0.0, spoken / (4.0 * len(sources))),
    )
    # Equal visual beats over the spoken interval. xfade overlaps each adjacent
    # pair by `transition`, so compensate source segment lengths accordingly.
    segment_duration = (spoken + transition * (len(sources) - 1)) / len(sources)

    cmd: list[str] = ["ffmpeg", "-y"]
    for source in sources:
        cmd += [
            "-loop",
            "1",
            "-framerate",
            str(fps),
            "-t",
            f"{segment_duration:.6f}",
            "-i",
            str(source),
        ]

    chains: list[str] = []
    normalize = _normalize_filter(width, height, fps)
    for idx in range(len(sources)):
        chains.append(f"[{idx}:v]{normalize},setpts=PTS-STARTPTS[v{idx}]")

    previous = "[v0]"
    for idx in range(1, len(sources)):
        out = f"[xf{idx}]"
        offset = idx * (segment_duration - transition)
        chains.append(
            f"{previous}[v{idx}]xfade=transition=fade:duration={transition:.6f}:"
            f"offset={offset:.6f}{out}"
        )
        previous = out

    final = "[vfinal]"
    chains.append(
        f"{previous}tpad=stop_mode=clone:stop_duration={pause:.6f},"
        f"trim=duration={render_slot:.6f},setpts=PTS-STARTPTS{final}"
    )
    cmd += ["-filter_complex", ";".join(chains), "-map", final, "-t", f"{render_slot:.6f}"]
    cmd += _encode_args(fps, crf, preset)
    cmd.append(str(output))
    _run(cmd, label=f"Render continuation scene {slot.scene_id}")


def _write_concat_list(paths: Iterable[Path], output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    list_path = output.with_suffix(".concat.txt")
    lines = []
    for path in paths:
        escaped = str(path.resolve()).replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
    list_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return list_path


def concat_scene_clips(paths: Sequence[Path], output: Path) -> None:
    if not paths:
        raise RenderError("No scene clips to concatenate")
    concat_file = _write_concat_list(paths, output)
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_file),
        "-an",
        "-c:v",
        "copy",
        "-movflags",
        "+faststart",
        str(output),
    ]
    _run(cmd, label=f"Concatenate {output.name}")


def generate_subtitle_plan(
    project_dir: Path,
    scenes: list[dict],
    slots: list[SceneSlot],
    words: list[dict],
    scene_words: dict[int, list[dict]],
    out_dir: Path,
    *,
    width: int,
    height: int,
    fps: int,
    mode: str,
    style: str,
) -> dict[str, list[tuple[Path, float, float]]]:
    # Import only after the macOS font runtime has been bootstrapped in main().
    from studio.rendering.scenes import generate_scene_subtitle_frames
    from studio.subtitles.subtitles import detect_devanagari_font_path, write_subtitle_overlay

    out_dir.mkdir(parents=True, exist_ok=True)
    font_path = detect_devanagari_font_path(project_dir)
    plan: dict[str, list[tuple[Path, float, float]]] = {}
    serializable: list[dict] = []
    previous_scene_ended_with_quote = False

    def plan_path_value(path: Path) -> str:
        try:
            return str(path.relative_to(project_dir))
        except ValueError:
            # Keeps the function testable with an external scratch directory.
            # Normal production output lives under project_dir/temp/.
            return str(path.resolve())

    for idx, (scene, slot) in enumerate(zip(scenes, slots)):
        if mode == "phrase" and ">" not in scene.get("text", ""):
            phrase_events = build_phrase_captions(
                scene_words[idx],
                scene_start=float(scene["start_time"]),
                scene_end=float(scene["end_time"]),
            )
            frames = []
            for phrase_idx, event in enumerate(phrase_events):
                png = out_dir / f"{slot.scene_id}-phrase-{phrase_idx:03d}.png"
                write_subtitle_overlay(
                    text=event.text,
                    out_path=png,
                    size=(width, height),
                    font_path=font_path,
                    full_text=event.text,
                    is_quote=False,
                    style=style,
                )
                frames.append((png, event.relative_start, event.relative_end))
        else:
            # Preserve the old, battle-tested cumulative/quote implementation as
            # an explicit compatibility mode and automatic quote fallback.
            frames = generate_scene_subtitle_frames(
                scene,
                words,
                out_dir,
                (width, height),
                font_path,
                clip_duration=slot.render_slot_duration(fps),
                prev_scene_ended_with_quote=previous_scene_ended_with_quote,
                style=style,
                scene_words=scene_words[idx],
            )
        plan[slot.scene_id] = frames
        previous_scene_ended_with_quote = ">" in scene.get("text", "")
        for png, rel_start, rel_end in frames:
            serializable.append(
                {
                    "scene_id": slot.scene_id,
                    "png": plan_path_value(png),
                    "relative_start": rel_start,
                    "relative_end": rel_end,
                    "absolute_start": slot.slot_start + rel_start,
                    "absolute_end": slot.slot_start + rel_end,
                }
            )

    plan_path = out_dir / "subtitle-plan.json"
    plan_path.write_text(
        json.dumps(
            {
                "version": 1,
                "mode": mode,
                "style": style,
                "width": width,
                "height": height,
                "entries": serializable,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return plan


def burn_subtitles(
    clean_clip: Path,
    subtitle_frames: Sequence[tuple[Path, float, float]],
    output: Path,
    *,
    duration: float,
    fps: int,
    crf: int,
    preset: str,
) -> None:
    from studio.subtitles.subtitles import subtitle_enable_expr

    cmd: list[str] = ["ffmpeg", "-y", "-i", str(clean_clip)]
    if not subtitle_frames:
        cmd += ["-t", f"{duration:.6f}"] + _encode_args(fps, crf, preset) + [str(output)]
        _run(cmd, label=f"Normalize captioned clip {output.stem}")
        return

    for png, _, _ in subtitle_frames:
        cmd += ["-loop", "1", "-framerate", str(fps), "-i", str(png)]

    chains: list[str] = []
    previous = "[0:v]"
    for idx, (_, start, end) in enumerate(subtitle_frames, start=1):
        out = f"[ov{idx}]"
        chains.append(
            f"{previous}[{idx}:v]overlay=0:0:"
            f"enable='{subtitle_enable_expr(start, end)}':format=auto{out}"
        )
        previous = out
    chains.append(f"{previous}format=yuv420p[vout]")
    cmd += [
        "-filter_complex",
        ";".join(chains),
        "-map",
        "[vout]",
        "-t",
        f"{duration:.6f}",
    ]
    cmd += _encode_args(fps, crf, preset)
    cmd.append(str(output))
    _run(cmd, label=f"Burn subtitles {output.stem}")


def mux_narration(captioned_master: Path, narration: Path, output: Path) -> None:
    video_duration = _probe_duration(captioned_master)
    narration_duration = _probe_duration(narration)
    frame_tolerance = 1.0 / DEFAULT_FPS + 0.02
    if video_duration + frame_tolerance < narration_duration:
        raise RenderError(
            f"Captioned video is shorter than narration: video={video_duration:.3f}s, "
            f"narration={narration_duration:.3f}s"
        )
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(captioned_master),
        "-i",
        str(narration),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-af",
        "apad",
        "-t",
        f"{video_duration:.6f}",
        "-movflags",
        "+faststart",
        str(output),
    ]
    _run(cmd, label="Mux narration")


def narration_path(project_dir: Path) -> Path:
    for name in ("narration.wav", "narration.mp3"):
        path = project_dir / "audio" / name
        if path.is_file():
            return path
    raise RenderError("Required narration not found: audio/narration.wav or audio/narration.mp3")


def validate_project(
    project_dir: Path,
) -> tuple[list[dict], list[dict], list[SceneSlot], list[SceneMedia], dict[int, list[dict]], float]:
    scenes_json = _read_json(project_dir / "scenes.json")
    timestamps_json = _read_json(project_dir / "audio" / "timestamps.json")
    manifest_json = _read_json(project_dir / "production-manifest.json")

    scenes = scenes_json.get("scenes")
    words = timestamps_json.get("words")
    assets = manifest_json.get("assets")
    if not isinstance(scenes, list):
        raise RenderError("scenes.json must contain a scenes list")
    if not isinstance(words, list):
        raise RenderError("timestamps.json must contain a words list")
    if not isinstance(assets, dict):
        raise RenderError("production-manifest.json must contain an assets object")

    narration = narration_path(project_dir)
    if not narration.is_file():
        raise RenderError(f"Required narration not found: {narration}")
    narration_duration = _probe_duration(narration)
    timestamp_duration = float(timestamps_json.get("duration") or narration_duration)
    if abs(narration_duration - timestamp_duration) > 0.15:
        raise RenderError(
            f"Narration/timestamp duration mismatch: {narration_duration:.3f}s vs {timestamp_duration:.3f}s"
        )

    slots = build_scene_slots(scenes, narration_duration)
    ownership = validate_word_ownership(scenes, words)
    media = resolve_all_media(project_dir, scenes, assets)
    return scenes, words, slots, media, ownership, narration_duration


def _render_summary(
    scenes: list[dict],
    words: list[dict],
    slots: list[SceneSlot],
    media: list[SceneMedia],
    narration_duration: float,
) -> str:
    video_count = sum(item.kind == "video" for item in media)
    image_count = len(media) - video_count
    continuation_assets = sum(max(0, len(item.paths) - 1) for item in media if item.kind == "images")
    pauses = sum(slot.pause_duration for slot in slots)
    return (
        f"Validated: {len(scenes)} scenes | {len(words)} words | "
        f"{video_count} generated-video scenes | {image_count} still scenes | "
        f"{continuation_assets} rendered continuation stills | "
        f"{pauses:.3f}s pause/hold time | {narration_duration:.3f}s total"
    )


def render_project(args: argparse.Namespace) -> Path:
    _assert_tooling()
    _ensure_macos_font_runtime()

    project_dir = Path(args.project_dir).expanduser().resolve()
    scenes, words, slots, media, ownership, narration_duration = validate_project(project_dir)
    print(_render_summary(scenes, words, slots, media, narration_duration), flush=True)
    if args.dry_run:
        print("Dry run complete: no render files written.", flush=True)
        return project_dir / "output" / "final-video-no-bgm.mp4"

    render_root = project_dir / "temp" / RENDER_NAMESPACE
    clean_dir = render_root / "scenes-clean"
    captioned_dir = render_root / "scenes-captioned"
    subtitle_dir = render_root / "subtitles"
    clean_dir.mkdir(parents=True, exist_ok=True)
    captioned_dir.mkdir(parents=True, exist_ok=True)
    subtitle_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "output").mkdir(parents=True, exist_ok=True)

    clean_clips: list[Path] = []
    for slot, item in zip(slots, media):
        output = clean_dir / f"{slot.scene_id}.mp4"
        clean_clips.append(output)
        if output.exists() and not args.force:
            print(f"  clean cached: {slot.scene_id}", flush=True)
            continue
        print(
            f"  clean render: {slot.scene_id} "
            f"({item.kind}; spoken={slot.spoken_duration:.2f}s, hold={slot.pause_duration:.2f}s)",
            flush=True,
        )
        if item.kind == "video":
            render_video_scene(
                item.paths[0],
                slot,
                output,
                width=args.width,
                height=args.height,
                fps=args.fps,
                crf=args.crf,
                preset=args.preset,
            )
        else:
            render_image_scene(
                item.paths,
                slot,
                output,
                width=args.width,
                height=args.height,
                fps=args.fps,
                crf=args.crf,
                preset=args.preset,
                continuation_fade=args.continuation_fade,
            )

    visual_master = project_dir / "temp" / "visual-master.mp4"
    print("→ Concatenating clean visual master (hard cuts between semantic scenes)...", flush=True)
    concat_scene_clips(clean_clips, visual_master)

    print("→ Generating subtitle plan with existing alignment/rendering logic...", flush=True)
    subtitle_plan = generate_subtitle_plan(
        project_dir,
        scenes,
        slots,
        words,
        ownership,
        subtitle_dir,
        width=args.width,
        height=args.height,
        fps=args.fps,
        mode=args.subtitle_mode,
        style=args.subtitle_style,
    )

    captioned_clips: list[Path] = []
    for slot, clean in zip(slots, clean_clips):
        output = captioned_dir / f"{slot.scene_id}.mp4"
        captioned_clips.append(output)
        if output.exists() and not args.force:
            print(f"  caption cached: {slot.scene_id}", flush=True)
            continue
        frames = subtitle_plan.get(slot.scene_id, [])
        print(f"  captions: {slot.scene_id} ({len(frames)} timed overlays)", flush=True)
        burn_subtitles(
            clean,
            frames,
            output,
            duration=slot.render_slot_duration(args.fps),
            fps=args.fps,
            crf=args.crf,
            preset=args.preset,
        )

    captioned_master = project_dir / "temp" / "captioned-master.mp4"
    print("→ Concatenating captioned master...", flush=True)
    concat_scene_clips(captioned_clips, captioned_master)

    output = project_dir / "output" / "final-video-no-bgm.mp4"
    if output.exists() and not args.force:
        print(f"✓ Final already exists: {output}", flush=True)
        return output
    print("→ Muxing narration only (no BGM)...", flush=True)
    mux_narration(captioned_master, narration_path(project_dir), output)
    duration = _probe_duration(output)
    size_mb = output.stat().st_size / (1024 * 1024)
    print(f"✓ Render complete: {output}", flush=True)
    print(f"  Duration: {duration:.3f}s | Size: {size_mb:.1f} MB", flush=True)
    print("  Audio: narration only; video stream is ready for later BGM remux.", flush=True)
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render KathaMind visuals + subtitles + narration, without background music or jitter"
    )
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--force", action="store_true", help="Re-render cached scene outputs")
    parser.add_argument("--dry-run", action="store_true", help="Validate timeline/assets/subtitles without rendering")
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT)
    parser.add_argument("--fps", type=int, default=DEFAULT_FPS)
    parser.add_argument("--crf", type=int, default=DEFAULT_CRF)
    parser.add_argument("--preset", default=DEFAULT_PRESET)
    parser.add_argument(
        "--continuation-fade",
        type=float,
        default=DEFAULT_CONTINUATION_FADE,
        help="Short dissolve, in seconds, only between continuation stills inside one scene",
    )
    parser.add_argument(
        "--subtitle-mode",
        choices=("phrase", "legacy-word"),
        default=DEFAULT_SUBTITLE_MODE,
        help=(
            "phrase keeps existing alignment but shows stable phrase captions; "
            "legacy-word preserves the older cumulative word-reveal presentation"
        ),
    )
    parser.add_argument(
        "--subtitle-style",
        choices=("soft_halo", "classic_card"),
        default=DEFAULT_SUBTITLE_STYLE,
        help="Pillow subtitle visual style; matching/timing remains unchanged",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.width <= 0 or args.height <= 0 or args.fps <= 0:
        parser.error("width/height/fps must be positive")
    if args.continuation_fade < 0:
        parser.error("--continuation-fade must be >= 0")
    try:
        render_project(args)
    except RenderError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


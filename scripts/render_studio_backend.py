#!/usr/bin/env python3
"""
Backend engine for Video Render Studio.
Handles media probing, thumbnail generation, video normalization,
in/out trimming, synthetic break generation, and FFmpeg concatenation.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
THUMBNAIL_DIR = PROJECT_ROOT / "temp" / ".thumbnails"


class RenderStudioError(Exception):
    """Raised when an operation in the render studio fails."""


def ensure_dirs() -> None:
    """Ensure output and cache directories exist."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)


def run_cmd(command: List[str]) -> subprocess.CompletedProcess[str]:
    """Execute a subprocess command and return completed process or raise RenderStudioError."""
    try:
        return subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RenderStudioError(f"Required binary missing: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        cmd_str = " ".join(shlex.quote(c) for c in command)
        raise RenderStudioError(f"Command failed:\n$ {cmd_str}\n\nError:\n{detail}") from exc


def get_media_info(video_path: Path) -> Dict[str, Any]:
    """Extract metadata using ffprobe."""
    if not video_path.is_file():
        raise RenderStudioError(f"File not found: {video_path}")

    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration,size,bit_rate",
        "-show_entries", "stream=codec_type,codec_name,width,height,r_frame_rate,duration",
        "-of", "json",
        str(video_path),
    ]
    result = run_cmd(cmd)
    try:
        data = json.loads(result.stdout)
        streams = data.get("streams", [])
        video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

        if not video_stream:
            raise RenderStudioError(f"No video stream found in {video_path}")

        duration = 0.0
        if "duration" in video_stream and video_stream["duration"]:
            try:
                duration = float(video_stream["duration"])
            except (ValueError, TypeError):
                pass
        if duration <= 0.0 and "format" in data and "duration" in data["format"]:
            try:
                duration = float(data["format"]["duration"])
            except (ValueError, TypeError):
                duration = 0.0

        width = int(video_stream.get("width", 1920))
        height = int(video_stream.get("height", 1080))

        fps = 30.0
        fps_str = video_stream.get("r_frame_rate", "30/1")
        if "/" in fps_str:
            num, den = fps_str.split("/", 1)
            try:
                fps = round(float(num) / float(den), 2) if float(den) != 0 else 30.0
            except (ValueError, ZeroDivisionError):
                fps = 30.0

        size_bytes = video_path.stat().st_size
        size_mb = round(size_bytes / (1024 * 1024), 2)

        return {
            "path": str(video_path.resolve()),
            "filename": video_path.name,
            "duration": round(duration, 3),
            "width": width,
            "height": height,
            "fps": fps,
            "has_audio": audio_stream is not None,
            "audio_codec": audio_stream.get("codec_name") if audio_stream else None,
            "video_codec": video_stream.get("codec_name"),
            "size_mb": size_mb,
        }
    except Exception as exc:
        raise RenderStudioError(f"Failed to probe {video_path}: {exc}") from exc


def generate_thumbnail(video_path: Path, force: bool = False) -> str:
    """Generate or retrieve a cached thumbnail for a video."""
    ensure_dirs()
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", str(video_path.resolve()))
    thumb_file = THUMBNAIL_DIR / f"{safe_name}.jpg"

    if thumb_file.exists() and not force and thumb_file.stat().st_size > 0:
        return str(thumb_file.resolve())

    # Try extracting at 1.0s or 0.1s
    for seek_time in ["00:00:01.000", "00:00:00.200", "00:00:00.000"]:
        try:
            cmd = [
                "ffmpeg",
                "-v", "error",
                "-y",
                "-ss", seek_time,
                "-i", str(video_path),
                "-vframes", "1",
                "-vf", "scale=320:-1",
                "-q:v", "3",
                str(thumb_file),
            ]
            run_cmd(cmd)
            if thumb_file.exists() and thumb_file.stat().st_size > 0:
                return str(thumb_file.resolve())
        except Exception:
            continue

    return ""


def list_available_videos(custom_paths: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Scan the repository for video files."""
    ensure_dirs()
    search_dirs = [
        PROJECT_ROOT / "videos",
        PROJECT_ROOT / "output",
        PROJECT_ROOT / "temp",
        PROJECT_ROOT / "projects",
        PROJECT_ROOT / "stories",
        PROJECT_ROOT / "tests",
    ]

    if custom_paths:
        for p in custom_paths:
            path_obj = Path(p).resolve()
            if path_obj.is_dir() and path_obj not in search_dirs:
                search_dirs.append(path_obj)

    seen_paths = set()
    found_videos = []

    valid_exts = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}

    for base_dir in search_dirs:
        if not base_dir.exists():
            continue
        try:
            for root, _, files in os.walk(base_dir):
                # Skip hidden directories like .git
                if "/." in root or "\\." in root:
                    continue
                for f in sorted(files):
                    ext = Path(f).suffix.lower()
                    if ext in valid_exts:
                        full_path = (Path(root) / f).resolve()
                        if full_path in seen_paths:
                            continue
                        seen_paths.add(full_path)

                        try:
                            info = get_media_info(full_path)
                            # Relative path display
                            try:
                                rel_path = str(full_path.relative_to(PROJECT_ROOT))
                            except ValueError:
                                rel_path = str(full_path)
                            info["relative_path"] = rel_path
                            rel_parent = str(Path(rel_path).parent)
                            info["folder_path"] = "" if rel_parent == "." else rel_parent
                            info["folder_parts"] = [p for p in Path(rel_path).parent.parts if p != "."]
                            info["category"] = _categorize_path(rel_path)
                            
                            # Generate thumbnail in background or on-demand
                            thumb_path = generate_thumbnail(full_path)
                            info["thumbnail_path"] = thumb_path
                            found_videos.append(info)
                        except Exception:
                            # If probe fails, continue to next file
                            continue
        except Exception:
            continue

    return found_videos


def _categorize_path(rel_path: str) -> str:
    """Categorize video for UI grouping."""
    parts = rel_path.split(os.sep)
    for container in ("projects", "stories"):
        if container in parts:
            idx = parts.index(container)
            if len(parts) > idx + 1:
                return f"Project: {parts[idx + 1]}"
    if "videos" in parts:
        return "Library Videos"
    if "output" in parts:
        return "Previous Exports"
    if "tests" in parts:
        return "Test Artifacts"
    if "temp" in parts:
        return "Temp Renders"
    return "Other Videos"


def build_synthetic_break(
    duration: float,
    width: int,
    height: int,
    fps: float,
    out_path: Path,
    color: str = "black",
) -> None:
    """Generate a clean synthetic solid-color video clip with silent stereo audio."""
    dur_str = f"{duration:.3f}"
    cmd = [
        "ffmpeg",
        "-v", "error",
        "-y",
        "-f", "lavfi",
        "-i", f"color=c={color}:s={width}x{height}:r={fps}:d={dur_str}",
        "-f", "lavfi",
        "-i", f"anullsrc=r=48000:cl=stereo",
        "-t", dur_str,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-ar", "48000",
        "-ac", "2",
        "-movflags", "+faststart",
        str(out_path),
    ]
    run_cmd(cmd)


def normalize_and_trim_clip(
    src_path: Path,
    start_sec: float,
    end_sec: Optional[float],
    width: int,
    height: int,
    fps: float,
    out_path: Path,
) -> None:
    """
    Trim and standardize a video clip into standard resolution, fps, pixel format,
    and 48kHz stereo AAC audio (generating silence if source lacks audio).
    """
    info = get_media_info(src_path)
    total_dur = info["duration"]

    start = max(0.0, start_sec)
    end = min(total_dur, end_sec) if end_sec is not None and end_sec > 0 else total_dur
    if end <= start:
        end = min(total_dur, start + 0.1)

    trim_duration = end - start
    dur_str = f"{trim_duration:.3f}"
    start_str = f"{start:.3f}"

    # Video filter: scale to fit within widthxheight while preserving aspect ratio, pad to center
    vf_scale_pad = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,"
        f"fps={fps},setsar=1"
    )

    if info["has_audio"]:
        # Has audio: slice both video and audio
        cmd = [
            "ffmpeg",
            "-v", "error",
            "-y",
            "-ss", start_str,
            "-t", dur_str,
            "-i", str(src_path),
            "-vf", vf_scale_pad,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-ar", "48000",
            "-ac", "2",
            "-movflags", "+faststart",
            str(out_path),
        ]
    else:
        # No audio: attach silent audio stream so concat works seamlessly
        cmd = [
            "ffmpeg",
            "-v", "error",
            "-y",
            "-ss", start_str,
            "-t", dur_str,
            "-i", str(src_path),
            "-f", "lavfi",
            "-i", "anullsrc=r=48000:cl=stereo",
            "-vf", vf_scale_pad,
            "-t", dur_str,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-ar", "48000",
            "-ac", "2",
            "-shortest",
            "-movflags", "+faststart",
            str(out_path),
        ]

    run_cmd(cmd)


def render_sequence(
    timeline_items: List[Dict[str, Any]],
    output_filename: str = "",
    target_width: int = 1920,
    target_height: int = 1080,
    target_fps: float = 30.0,
    watermark_image: Optional[str] = None,
    log_callback: Optional[Callable[[str, str], None]] = None,
) -> Dict[str, Any]:
    """
    Assemble the complete sequence:
    1. Trims and normalizes all clips and breaks.
    2. Concatenates into a seamless MP4.
    3. Optionally overlays watermark badge.
    4. Writes final file to PROJECT_ROOT / "output" / output_filename.
    """
    ensure_dirs()

    def log(msg: str, msg_type: str = "info"):
        if log_callback:
            log_callback(msg, msg_type)

    if not timeline_items:
        raise RenderStudioError("Timeline is empty. Please add at least one video or break.")

    if not output_filename or not output_filename.strip():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"render_{timestamp}.mp4"

    if not output_filename.lower().endswith(".mp4"):
        output_filename += ".mp4"

    final_output_path = OUTPUT_DIR / output_filename

    log(f"🎬 Starting render pipeline for {len(timeline_items)} timeline items...", "header")
    log(f"📐 Target Resolution: {target_width}x{target_height} @ {target_fps}fps", "info")
    log(f"💾 Output Destination: {final_output_path}", "info")

    start_total_time = time.time()

    with tempfile.TemporaryDirectory(prefix="render-studio-") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        normalized_chunks: List[Path] = []

        for idx, item in enumerate(timeline_items):
            item_type = item.get("type", "clip")
            chunk_path = temp_dir / f"chunk_{idx:03d}.mp4"
            log(f"⏳ Processing item #{idx + 1}/{len(timeline_items)}: [{item_type.upper()}]...", "info")

            if item_type == "break":
                duration = float(item.get("duration", 1.0))
                duration = max(0.1, duration)
                color = item.get("color", "black")
                log(f"   ➕ Generating synthetic break ({duration:.2f}s, color: {color})", "info")
                build_synthetic_break(
                    duration=duration,
                    width=target_width,
                    height=target_height,
                    fps=target_fps,
                    out_path=chunk_path,
                    color=color,
                )
            else:
                # Video Clip
                src_path_str = item.get("path", "")
                src_path = Path(src_path_str).resolve()
                if not src_path.is_file():
                    raise RenderStudioError(f"Timeline item #{idx + 1} video not found: {src_path}")

                start_sec = float(item.get("start", 0.0))
                end_sec = float(item["end"]) if item.get("end") is not None else None

                log(
                    f"   ✂️ Trimming '{src_path.name}': {start_sec:.2f}s ➡️ {end_sec or 'end':.2f}s",
                    "info",
                )
                normalize_and_trim_clip(
                    src_path=src_path,
                    start_sec=start_sec,
                    end_sec=end_sec,
                    width=target_width,
                    height=target_height,
                    fps=target_fps,
                    out_path=chunk_path,
                )

            normalized_chunks.append(chunk_path)

        # Concatenate normalized chunks
        concat_list_file = temp_dir / "concat_list.txt"
        with concat_list_file.open("w", encoding="utf-8") as f:
            for p in normalized_chunks:
                escaped = str(p.resolve()).replace("'", "'\\''")
                f.write(f"file '{escaped}'\n")

        raw_concat_output = temp_dir / "concatenated.mp4"
        log("🔄 Concatenating all normalized chunks...", "info")

        concat_cmd = [
            "ffmpeg",
            "-v", "error",
            "-y",
            "-fflags", "+genpts",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list_file),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-ar", "48000",
            "-ac", "2",
            "-movflags", "+faststart",
            str(raw_concat_output),
        ]
        run_cmd(concat_cmd)

        # Apply Watermark if requested
        if watermark_image and Path(watermark_image).is_file():
            log(f"💧 Applying watermark overlay from {Path(watermark_image).name}...", "info")
            watermark_path = Path(watermark_image).resolve()
            watermarked_output = temp_dir / "watermarked.mp4"

            # Overlay watermark in bottom-right corner with 24px padding and subtle opacity
            wm_cmd = [
                "ffmpeg",
                "-v", "error",
                "-y",
                "-i", str(raw_concat_output),
                "-i", str(watermark_path),
                "-filter_complex", "[1:v]scale=160:-1[wm];[0:v][wm]overlay=W-w-24:H-h-24:format=auto[outv]",
                "-map", "[outv]",
                "-map", "0:a",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-c:a", "copy",
                "-movflags", "+faststart",
                str(watermarked_output),
            ]
            run_cmd(wm_cmd)
            # Move to final location
            if final_output_path.exists():
                final_output_path.unlink()
            watermarked_output.rename(final_output_path)
        else:
            # Direct move
            if final_output_path.exists():
                final_output_path.unlink()
            raw_concat_output.rename(final_output_path)

    elapsed = round(time.time() - start_total_time, 2)
    output_info = get_media_info(final_output_path)
    output_info["render_time_sec"] = elapsed

    log(f"✅ Render complete in {elapsed}s!", "success")
    log(f"📦 Final Output: {final_output_path.name} ({output_info['duration']}s, {output_info['size_mb']}MB)", "success")

    return output_info


def open_in_finder(file_or_dir_path: str) -> None:
    """Reveal file or folder in macOS Finder."""
    path = Path(file_or_dir_path).resolve()
    if path.is_file():
        subprocess.run(["open", "-R", str(path)])
    elif path.is_dir():
        subprocess.run(["open", str(path)])
    else:
        subprocess.run(["open", str(OUTPUT_DIR)])


def play_video(file_path: str) -> None:
    """Launch video in macOS default player."""
    path = Path(file_path).resolve()
    if path.is_file():
        subprocess.run(["open", str(path)])


def format_size(size_bytes: int) -> str:
    """Format bytes into readable size."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def classify_file_type(path: Path) -> str:
    """Classify file extension into semantic UI types."""
    ext = path.suffix.lower()
    if ext in {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}:
        return "video"
    if ext in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".bmp"}:
        return "image"
    if ext in {".mp3", ".wav", ".aac", ".m4a", ".ogg", ".flac", ".aiff"}:
        return "audio"
    if ext in {".md", ".markdown"}:
        return "markdown"
    if ext == ".py":
        return "python"
    if ext == ".json":
        return "json"
    if ext in {".html", ".htm", ".css", ".js", ".jsx", ".ts", ".tsx", ".toml", ".yaml", ".yml", ".sh", ".sql", ".scpt"}:
        return "code"
    if ext in {".txt", ".log", ".csv", ".tsv", ".ini", ".env", ".gitignore"}:
        return "text"
    if ext in {".pdf", ".doc", ".docx"}:
        return "document"
    return "other"


def list_all_project_files(custom_root: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Recursively list all project files across the repository."""
    ensure_dirs()
    root_path = (custom_root or PROJECT_ROOT).resolve()

    excluded_dirs = {".git", "__pycache__", ".venv", "node_modules", ".pytest_cache"}
    excluded_files = {".DS_Store"}

    all_files: List[Dict[str, Any]] = []

    for root, dirs, files in os.walk(root_path):
        # Exclude hidden / cache directories
        dirs[:] = [d for d in dirs if d not in excluded_dirs and not d.startswith(".")]

        for f in sorted(files):
            if f in excluded_files:
                continue

            file_path = (Path(root) / f).resolve()
            if not file_path.is_file():
                continue

            try:
                rel_path = str(file_path.relative_to(PROJECT_ROOT))
            except ValueError:
                rel_path = str(file_path)

            rel_parent = str(Path(rel_path).parent)
            folder_path = "" if rel_parent == "." else rel_parent
            folder_parts = [p for p in Path(rel_path).parent.parts if p != "."]

            size_bytes = file_path.stat().st_size
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            file_type = classify_file_type(file_path)

            item: Dict[str, Any] = {
                "path": str(file_path),
                "filename": f,
                "relative_path": rel_path,
                "folder_path": folder_path,
                "folder_parts": folder_parts,
                "category": _categorize_path(rel_path),
                "ext": file_path.suffix.lower(),
                "file_type": file_type,
                "size_bytes": size_bytes,
                "size_formatted": format_size(size_bytes),
                "modified_time": mtime,
            }

            # Enrich videos with ffprobe metadata & thumbnails
            if file_type == "video":
                try:
                    info = get_media_info(file_path)
                    item["duration"] = info["duration"]
                    item["width"] = info["width"]
                    item["height"] = info["height"]
                    item["fps"] = info["fps"]
                    item["size_mb"] = info["size_mb"]
                    item["has_audio"] = info["has_audio"]
                    item["thumbnail_path"] = generate_thumbnail(file_path)
                except Exception:
                    item["duration"] = 0.0
                    item["width"] = 0
                    item["height"] = 0
                    item["fps"] = 0.0
                    item["size_mb"] = round(size_bytes / (1024 * 1024), 2)
                    item["thumbnail_path"] = ""

            all_files.append(item)

    return all_files


def read_project_file_content(path_or_rel: str) -> Dict[str, Any]:
    """Read and return content of text/markdown/python/json files safely."""
    path = Path(path_or_rel)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    path = path.resolve()

    if not path.is_file():
        raise RenderStudioError(f"File not found: {path}")

    size_bytes = path.stat().st_size
    file_type = classify_file_type(path)

    # If file is larger than 2MB, truncate or avoid full text load
    max_size = 2 * 1024 * 1024
    if size_bytes > max_size:
        return {
            "path": str(path),
            "filename": path.name,
            "file_type": file_type,
            "size_formatted": format_size(size_bytes),
            "content": f"<!-- File is too large to preview ({format_size(size_bytes)}). Size exceeds 2MB limit. -->",
            "lines_count": 0,
            "is_truncated": True,
        }

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
        lines_count = len(content.splitlines())
        return {
            "path": str(path),
            "filename": path.name,
            "file_type": file_type,
            "size_formatted": format_size(size_bytes),
            "content": content,
            "lines_count": lines_count,
            "is_truncated": False,
        }
    except Exception as exc:
        raise RenderStudioError(f"Cannot read file {path}: {exc}") from exc

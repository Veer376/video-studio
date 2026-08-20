#!/usr/bin/env python3
"""Frame-accurate video cutting and removal CLI utility.

Supports explicit and unambiguous operations:
  --cut / --remove / --delete <range> : Cut out and remove a section (head, middle, or tail)
  --cut-start / --drop-start <secs>   : Shorthand to cut off N seconds from the start
  --cut-end / --drop-end <secs>       : Shorthand to cut off N seconds from the end
  --keep <range>                      : Keep only this window, discard everything outside
  --start / --end / --duration        : Explicit in/out bounds to keep

Safe atomic in-place replacement, optional backup, audio auto-detection,
optional fades, and dry-run preview.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


class CutError(Exception):
    """Raised when video probing, validation, or cutting fails."""


@dataclass(frozen=True)
class MediaInfo:
    duration: float
    width: int | None
    height: int | None
    has_video: bool
    has_audio: bool
    codec_name: str | None


def parse_time(val: str | float | int | None) -> float | None:
    """Parse a timestamp string into float seconds.

    Supported formats:
      - Seconds: "5", "5.5", "123.45"
      - MM:SS[.ms]: "01:23", "1:23.5", "0:0.5"
      - HH:MM:SS[.ms]: "01:02:03", "00:01:23.500"
    """
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)

    s = str(val).strip()
    if not s:
        return None

    try:
        return float(s)
    except ValueError:
        pass

    parts = s.split(":")
    if len(parts) == 2:  # MM:SS
        try:
            m = float(parts[0])
            sec = float(parts[1])
            return m * 60.0 + sec
        except ValueError:
            pass
    elif len(parts) == 3:  # HH:MM:SS
        try:
            h = float(parts[0])
            m = float(parts[1])
            sec = float(parts[2])
            return h * 3600.0 + m * 60.0 + sec
        except ValueError:
            pass

    raise CutError(
        f"Invalid timestamp format: {val!r}. Use seconds (e.g. 2.5), MM:SS (e.g. 01:30), or HH:MM:SS (e.g. 00:01:30)."
    )


def parse_range(range_str: str | None) -> tuple[float | None, float | None, float | None]:
    """Parse a time range string into (start_sec, end_sec, duration_sec).

    Supported formats:
      - "2.5:7.5", ":5.0", "2.5:"
      - "2.0+4.5" (start + duration)
      - "1.5..4.5"
      - "00:01:00:05" (clock format range)
    """
    if not range_str:
        return None, None, None

    s = range_str.strip()
    start: float | None = None
    end: float | None = None
    duration: float | None = None

    if "+" in s:
        left, right = s.split("+", 1)
        start = parse_time(left) if left else 0.0
        duration = parse_time(right)
        if start is not None and duration is not None:
            end = start + duration
    elif ".." in s:
        left, right = s.split("..", 1)
        start = parse_time(left) if left else 0.0
        end = parse_time(right) if right else None
    elif "-" in s and not s.startswith("-"):
        parts = s.split("-")
        if len(parts) == 2:
            left, right = parts[0].strip(), parts[1].strip()
            start = parse_time(left) if left else 0.0
            end = parse_time(right) if right else None
    elif ":" in s:
        parts = s.split(":")
        if len(parts) == 2:
            left, right = parts[0].strip(), parts[1].strip()
            start = parse_time(left) if left else 0.0
            end = parse_time(right) if right else None
        elif len(parts) == 4:  # MM:SS:MM:SS
            left = f"{parts[0]}:{parts[1]}"
            right = f"{parts[2]}:{parts[3]}"
            start = parse_time(left)
            end = parse_time(right)
        elif len(parts) == 6:  # HH:MM:SS:HH:MM:SS
            left = f"{parts[0]}:{parts[1]}:{parts[2]}"
            right = f"{parts[3]}:{parts[4]}:{parts[5]}"
            start = parse_time(left)
            end = parse_time(right)
        else:
            raise CutError(
                f"Ambiguous range format: {range_str!r}. Use 'start:end' (e.g. 2.5:7.0) or 'start+duration' (e.g. 2.5+4.5)."
            )
    else:
        start = 0.0
        end = parse_time(s)

    if start is not None and end is not None and duration is None:
        duration = end - start

    return start, end, duration


def resolve_keep_segments(
    total_duration: float,
    *,
    keep_str: str | None = None,
    cut_str: str | None = None,
    cut_start_sec: float | None = None,
    cut_end_sec: float | None = None,
    explicit_start: float | None = None,
    explicit_end: float | None = None,
    explicit_duration: float | None = None,
) -> tuple[list[tuple[float, float]], str]:
    """Resolve the requested edit into a list of (start_sec, end_sec) segments to keep.

    Returns (segments_to_keep, operation_description).
    """
    has_cut = cut_str is not None or cut_start_sec is not None or cut_end_sec is not None
    has_keep = keep_str is not None or explicit_start is not None or explicit_end is not None or explicit_duration is not None

    if has_cut and has_keep:
        raise CutError(
            "Conflicting arguments: Cannot combine --cut/--cut-start/--cut-end with --keep/--start/--end in the same command."
        )

    # 1. Handle CUT operations
    if has_cut:
        cut_start: float | None = None
        cut_end: float | None = None

        if cut_start_sec is not None:
            cut_start = 0.0
            cut_end = cut_start_sec
        elif cut_end_sec is not None:
            cut_start = max(0.0, total_duration - cut_end_sec)
            cut_end = total_duration
        elif cut_str is not None:
            c_s, c_e, _ = parse_range(cut_str)
            cut_start = 0.0 if c_s is None else c_s
            cut_end = total_duration if c_e is None else c_e

        if cut_start is None or cut_end is None:
            raise CutError("Invalid cut parameters.")

        cut_start = max(0.0, min(total_duration, cut_start))
        cut_end = max(0.0, min(total_duration, cut_end))

        if cut_start >= cut_end:
            raise CutError(
                f"Invalid cut range: [{cut_start:.2f}s, {cut_end:.2f}s]. Cut start must be before cut end."
            )

        cut_dur = cut_end - cut_start
        segments: list[tuple[float, float]] = []

        # Case A: Cut from the beginning (0 -> cut_end)
        if cut_start == 0.0:
            if cut_end < total_duration:
                segments.append((cut_end, total_duration))
            desc = f"CUT HEAD: removed first {cut_dur:.2f}s (0.00s -> {cut_end:.2f}s), keeping remaining {total_duration - cut_dur:.2f}s ({cut_end:.2f}s -> {total_duration:.2f}s)"
        # Case B: Cut at the end (cut_start -> total_duration)
        elif cut_end >= total_duration:
            segments.append((0.0, cut_start))
            desc = f"CUT TAIL: removed last {cut_dur:.2f}s ({cut_start:.2f}s -> {total_duration:.2f}s), keeping first {cut_start:.2f}s (0.00s -> {cut_start:.2f}s)"
        # Case C: Middle cut (0 -> cut_start and cut_end -> total_duration)
        else:
            segments.append((0.0, cut_start))
            segments.append((cut_end, total_duration))
            desc = f"CUT MIDDLE: removed {cut_dur:.2f}s ({cut_start:.2f}s -> {cut_end:.2f}s), splicing [0.00s -> {cut_start:.2f}s] + [{cut_end:.2f}s -> {total_duration:.2f}s]"

        if not segments:
            raise CutError(f"Cut range [{cut_start:.2f}s, {cut_end:.2f}s] covers the entire video duration.")

        return segments, desc

    # 2. Handle KEEP operations
    start_sec, end_sec, target_dur = parse_range(keep_str)

    if explicit_start is not None:
        start_sec = explicit_start
    if explicit_end is not None:
        end_sec = explicit_end
    if explicit_duration is not None:
        target_dur = explicit_duration
        if start_sec is not None and end_sec is None:
            end_sec = start_sec + target_dur
        elif start_sec is None and end_sec is not None:
            start_sec = max(0.0, end_sec - target_dur)

    if start_sec is None:
        start_sec = 0.0
    if end_sec is None:
        end_sec = total_duration

    start_sec = max(0.0, min(total_duration, start_sec))
    end_sec = max(0.0, min(total_duration, end_sec))

    if start_sec >= end_sec:
        raise CutError(
            f"Invalid keep range: [{start_sec:.2f}s, {end_sec:.2f}s]. Start must be less than end. Total video duration is {total_duration:.2f}s."
        )

    keep_dur = end_sec - start_sec
    desc = f"KEEP WINDOW: keeping {keep_dur:.2f}s ({start_sec:.2f}s -> {end_sec:.2f}s), discarding outside"
    return [(start_sec, end_sec)], desc


def get_media_info(video_path: Path) -> MediaInfo:
    """Probe video metadata using ffprobe."""
    if not video_path.is_file():
        raise CutError(f"Video file not found: {video_path}")

    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-show_entries", "stream=codec_type,codec_name,width,height",
        "-of", "json",
        str(video_path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except FileNotFoundError as exc:
        raise CutError("Required binary 'ffprobe' not found. Ensure FFmpeg is installed and on PATH.") from exc
    except subprocess.CalledProcessError as exc:
        err = (exc.stderr or exc.stdout or "").strip()
        raise CutError(f"ffprobe failed on {video_path}: {err}") from exc

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise CutError(f"Failed to parse ffprobe output for {video_path}: {proc.stdout}") from exc

    format_info = data.get("format", {})
    streams = data.get("streams", [])

    duration_str = format_info.get("duration")
    if not duration_str:
        duration_str = next(
            (s.get("duration") for s in streams if s.get("duration")), None
        )

    if not duration_str:
        raise CutError(f"Could not determine duration for video: {video_path}")

    duration = float(duration_str)
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    if not video_stream:
        raise CutError(f"No video stream found in {video_path}")

    width = int(video_stream.get("width", 0)) if video_stream.get("width") else None
    height = int(video_stream.get("height", 0)) if video_stream.get("height") else None
    codec_name = video_stream.get("codec_name")

    return MediaInfo(
        duration=duration,
        width=width,
        height=height,
        has_video=True,
        has_audio=bool(audio_stream),
        codec_name=codec_name,
    )


def build_ffmpeg_cmd(
    input_path: Path,
    output_path: Path,
    segments: list[tuple[float, float]],
    has_audio: bool,
    crf: int = 18,
    fade_in: float = 0.0,
    fade_out: float = 0.0,
) -> list[str]:
    """Build the frame-accurate FFmpeg command.

    - Single segment: uses fast -ss and -t with encoding and fades.
    - Multiple segments (middle cuts): uses filter_complex trim + concat to splice segments.
    """
    total_out_duration = sum(end - start for start, end in segments)

    if len(segments) == 1:
        start_sec, end_sec = segments[0]
        dur = end_sec - start_sec

        cmd = [
            "ffmpeg",
            "-y",
            "-ss", f"{start_sec:.4f}",
            "-i", str(input_path),
            "-t", f"{dur:.4f}",
        ]

        video_filters: list[str] = []
        if fade_in > 0:
            video_filters.append(f"fade=t=in:st=0:d={fade_in:.3f}")
        if fade_out > 0:
            out_start = max(0.0, dur - fade_out)
            video_filters.append(f"fade=t=out:st={out_start:.3f}:d={fade_out:.3f}")

        if video_filters:
            cmd.extend(["-vf", ",".join(video_filters)])

        cmd.extend([
            "-c:v", "libx264",
            "-crf", str(crf),
            "-preset", "fast",
            "-pix_fmt", "yuv420p",
            "-avoid_negative_ts", "make_zero",
        ])

        if has_audio:
            audio_filters: list[str] = []
            if fade_in > 0:
                audio_filters.append(f"afade=t=in:st=0:d={fade_in:.3f}")
            if fade_out > 0:
                out_start = max(0.0, dur - fade_out)
                audio_filters.append(f"afade=t=out:st={out_start:.3f}:d={fade_out:.3f}")

            if audio_filters:
                cmd.extend(["-af", ",".join(audio_filters)])

            cmd.extend(["-c:a", "aac", "-b:a", "192k"])
        else:
            cmd.append("-an")

        cmd.append(str(output_path))
        return cmd

    # Multiple segments (Middle cut splice)
    filter_parts: list[str] = []
    v_labels: list[str] = []
    a_labels: list[str] = []

    for i, (s, e) in enumerate(segments):
        v_lbl = f"v{i}"
        filter_parts.append(f"[0:v]trim=start={s:.4f}:end={e:.4f},setpts=PTS-STARTPTS[{v_lbl}]")
        v_labels.append(f"[{v_lbl}]")

        if has_audio:
            a_lbl = f"a{i}"
            filter_parts.append(f"[0:a]atrim=start={s:.4f}:end={e:.4f},asetpts=PTS-STARTPTS[{a_lbl}]")
            a_labels.append(f"[{a_lbl}]")

    n_segs = len(segments)
    if has_audio:
        concat_in = "".join(f"{v_labels[i]}{a_labels[i]}" for i in range(n_segs))
        concat_str = f"{concat_in}concat=n={n_segs}:v=1:a=1[v_cat][a_cat]"
        final_v = "[v_cat]"
        final_a = "[a_cat]"
    else:
        concat_in = "".join(v_labels)
        concat_str = f"{concat_in}concat=n={n_segs}:v=1:a=0[v_cat]"
        final_v = "[v_cat]"
        final_a = None

    filter_parts.append(concat_str)

    if fade_in > 0 or fade_out > 0:
        v_fades = []
        if fade_in > 0:
            v_fades.append(f"fade=t=in:st=0:d={fade_in:.3f}")
        if fade_out > 0:
            out_start = max(0.0, total_out_duration - fade_out)
            v_fades.append(f"fade=t=out:st={out_start:.3f}:d={fade_out:.3f}")
        filter_parts.append(f"{final_v}{','.join(v_fades)}[v_out]")
        final_v = "[v_out]"

        if has_audio:
            a_fades = []
            if fade_in > 0:
                a_fades.append(f"afade=t=in:st=0:d={fade_in:.3f}")
            if fade_out > 0:
                out_start = max(0.0, total_out_duration - fade_out)
                a_fades.append(f"afade=t=out:st={out_start:.3f}:d={fade_out:.3f}")
            filter_parts.append(f"{final_a}{','.join(a_fades)}[a_out]")
            final_a = "[a_out]"

    full_filter = "; ".join(filter_parts)

    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(input_path),
        "-filter_complex", full_filter,
        "-map", final_v,
    ]
    if has_audio and final_a:
        cmd.extend(["-map", final_a])

    cmd.extend([
        "-c:v", "libx264",
        "-crf", str(crf),
        "-preset", "fast",
        "-pix_fmt", "yuv420p",
    ])

    if has_audio:
        cmd.extend(["-c:a", "aac", "-b:a", "192k"])
    else:
        cmd.append("-an")

    cmd.append(str(output_path))
    return cmd


def cut_video(
    input_path: Path,
    output_path: Path | None = None,
    *,
    keep_str: str | None = None,
    cut_str: str | None = None,
    cut_start_sec: float | None = None,
    cut_end_sec: float | None = None,
    start: float | None = None,
    end: float | None = None,
    duration: float | None = None,
    crf: int = 18,
    fade_in: float = 0.0,
    fade_out: float = 0.0,
    backup: bool = False,
    dry_run: bool = False,
) -> Path:
    """Cut or edit a single video with frame accuracy, safe atomic in-place replacement, and verification."""
    resolved_input = input_path.resolve()
    if not resolved_input.is_file():
        raise CutError(f"Input file does not exist: {resolved_input}")

    # Probe media info
    info = get_media_info(resolved_input)

    # Resolve segments to keep
    segments, op_desc = resolve_keep_segments(
        total_duration=info.duration,
        keep_str=keep_str,
        cut_str=cut_str,
        cut_start_sec=cut_start_sec,
        cut_end_sec=cut_end_sec,
        explicit_start=start,
        explicit_end=end,
        explicit_duration=duration,
    )

    total_out_duration = sum(e - s for s, e in segments)
    is_in_place = output_path is None or output_path.resolve() == resolved_input
    final_output = resolved_input if is_in_place else output_path.resolve()

    if dry_run:
        print(f"\n[DRY RUN] Plan for: {resolved_input}")
        print(f"  • Operation       : {op_desc}")
        print(f"  • Source duration : {info.duration:.3f}s ({info.width}x{info.height}, audio={info.has_audio})")
        print(f"  • Kept segments   : {', '.join(f'[{s:.2f}s -> {e:.2f}s]' for s, e in segments)}")
        print(f"  • Output duration : {total_out_duration:.3f}s")
        print(f"  • Destination     : {final_output} {'(In-place replace)' if is_in_place else ''}")
        if is_in_place and backup:
            print(f"  • Backup file     : {resolved_input.with_name(resolved_input.stem + '.orig' + resolved_input.suffix)}")
        if fade_in > 0 or fade_out > 0:
            print(f"  • Transitions     : Fade-in={fade_in:.2f}s, Fade-out={fade_out:.2f}s")

        preview_cmd = build_ffmpeg_cmd(
            input_path=resolved_input,
            output_path=final_output if not is_in_place else Path("/tmp/preview_output.mp4"),
            segments=segments,
            has_audio=info.has_audio,
            crf=crf,
            fade_in=fade_in,
            fade_out=fade_out,
        )
        print(f"  • FFmpeg command  :\n    $ {' '.join(shlex.quote(c) for c in preview_cmd)}\n")
        return final_output

    final_output.parent.mkdir(parents=True, exist_ok=True)

    # In-place safety: write to temporary file first
    if is_in_place:
        temp_fd, temp_file_str = tempfile.mkstemp(
            prefix=f".{resolved_input.stem}_cut_",
            suffix=resolved_input.suffix,
            dir=str(resolved_input.parent),
        )
        os.close(temp_fd)
        work_output = Path(temp_file_str)
    else:
        work_output = final_output

    try:
        ffmpeg_cmd = build_ffmpeg_cmd(
            input_path=resolved_input,
            output_path=work_output,
            segments=segments,
            has_audio=info.has_audio,
            crf=crf,
            fade_in=fade_in,
            fade_out=fade_out,
        )

        print(f"Processing {resolved_input.name}: {op_desc}...")
        proc = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "").strip()
            raise CutError(f"FFmpeg failed:\n{err}")

        if not work_output.is_file() or work_output.stat().st_size == 0:
            raise CutError(f"FFmpeg completed but generated an empty or missing output file: {work_output}")

        if is_in_place:
            if backup:
                backup_path = resolved_input.with_name(f"{resolved_input.stem}.orig{resolved_input.suffix}")
                shutil.copy2(resolved_input, backup_path)
                print(f"  Created backup: {backup_path.name}")

            shutil.move(str(work_output), str(final_output))

        out_info = get_media_info(final_output)
        print(f"✓ Saved: {final_output} (duration: {out_info.duration:.2f}s, size: {final_output.stat().st_size:,} bytes)")
        return final_output

    except Exception:
        if is_in_place and work_output.is_file():
            try:
                work_output.unlink(missing_ok=True)
            except Exception:
                pass
        raise


def resolve_inputs(patterns: Sequence[str]) -> list[Path]:
    """Expand input patterns and globs into a list of existing files."""
    results: list[Path] = []
    for pat in patterns:
        expanded = glob.glob(pat, recursive=True)
        if expanded:
            for p in expanded:
                path_obj = Path(p)
                if path_obj.is_file() and path_obj not in results:
                    results.append(path_obj)
        else:
            path_obj = Path(pat)
            if path_obj.is_file() and path_obj not in results:
                results.append(path_obj)
            elif not path_obj.exists():
                raise CutError(f"Input file not found: {pat}")
    return results


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Frame-accurate video cutting and removal utility."
    )
    parser.add_argument(
        "-i", "--input",
        dest="inputs",
        action="append",
        required=True,
        help="Input video file path or glob pattern (repeatable)",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Output video file path (if omitted, replaces input in-place)",
    )

    # CUT / REMOVE options
    cut_group = parser.add_argument_group("Cut / Remove Options (discards specified time, keeps rest)")
    cut_group.add_argument(
        "-c", "--cut", "--remove", "--delete",
        dest="cut",
        default=None,
        help="Cut out and remove time range: 'start:end' (e.g. 0:2.5 or 3.0:5.0)",
    )
    cut_group.add_argument(
        "--cut-start", "--drop-start",
        type=parse_time,
        default=None,
        help="Cut off N seconds from the start of the video (e.g. 2.5)",
    )
    cut_group.add_argument(
        "--cut-end", "--drop-end",
        type=parse_time,
        default=None,
        help="Cut off N seconds from the end of the video (e.g. 1.5)",
    )

    # KEEP options
    keep_group = parser.add_argument_group("Keep Options (keeps specified time window, discards outside)")
    keep_group.add_argument(
        "-k", "--keep",
        default=None,
        help="Keep only time range: 'start:end' (e.g. 2.5:10.0 or 2+5)",
    )
    keep_group.add_argument(
        "-s", "--start",
        type=parse_time,
        default=None,
        help="Keep start timestamp (seconds or MM:SS / HH:MM:SS)",
    )
    keep_group.add_argument(
        "-e", "--end", "--to",
        dest="end",
        type=parse_time,
        default=None,
        help="Keep end timestamp (seconds or MM:SS / HH:MM:SS)",
    )
    keep_group.add_argument(
        "-d", "--duration",
        type=parse_time,
        default=None,
        help="Keep target duration from start (seconds)",
    )

    # Quality and transitions
    parser.add_argument(
        "--crf",
        type=int,
        default=18,
        help="H.264 quality CRF (default: 18 for high visual fidelity)",
    )
    parser.add_argument(
        "--fade-in",
        type=float,
        default=0.0,
        help="Fade-in duration in seconds for video & audio (default: 0.0)",
    )
    parser.add_argument(
        "--fade-out",
        type=float,
        default=0.0,
        help="Fade-out duration in seconds for video & audio (default: 0.0)",
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="When replacing in-place, save original copy as <name>.orig.mp4",
    )
    parser.add_argument(
        "-n", "--dry-run",
        action="store_true",
        help="Print calculated plan and FFmpeg command without executing",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        input_files = resolve_inputs(args.inputs)
        if not input_files:
            raise CutError("No valid input files found.")

        if len(input_files) > 1 and args.output and not args.dry_run:
            raise CutError("Cannot specify a single --output when processing multiple input files. Omit --output for in-place cutting.")

        for vid in input_files:
            cut_video(
                input_path=vid,
                output_path=args.output if len(input_files) == 1 else None,
                keep_str=args.keep,
                cut_str=args.cut,
                cut_start_sec=args.cut_start,
                cut_end_sec=args.cut_end,
                start=args.start,
                end=args.end,
                duration=args.duration,
                crf=args.crf,
                fade_in=args.fade_in,
                fade_out=args.fade_out,
                backup=args.backup,
                dry_run=args.dry_run,
            )
        return 0

    except CutError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Mix background music beneath dialogue with smooth sidechain ducking.

The input video's original audio is preserved as the foreground track. A
speech-focused copy of that audio controls a compressor on the music, lowering
the score during dialogue and allowing it to recover naturally during pauses.
"""

from __future__ import annotations

import argparse
import json
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class BackgroundMusicError(RuntimeError):
    """Raised when the background-music mix cannot be produced safely."""


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise BackgroundMusicError(f"Required executable is missing: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout).strip()
        rendered = " ".join(shlex.quote(part) for part in command)
        raise BackgroundMusicError(f"Command failed: {rendered}\n{detail}") from exc


def probe(path: Path) -> dict[str, Any]:
    result = run([
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration,size",
        "-show_entries",
        "stream=codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels",
        "-of",
        "json",
        str(path),
    ])
    try:
        data = json.loads(result.stdout)
        duration = float(data["format"]["duration"])
        streams = data["streams"]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise BackgroundMusicError(f"Could not inspect media file {path}: {exc}") from exc
    return {"duration": duration, "streams": streams, "raw": data}


def has_stream(info: dict[str, Any], stream_type: str) -> bool:
    return any(stream.get("codec_type") == stream_type for stream in info["streams"])


def number(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def build_filter(
    duration: float,
    music_volume_db: float,
    key_boost_db: float,
    threshold: float,
    ratio: float,
    attack_ms: float,
    release_ms: float,
    detector_highpass_hz: int,
    detector_lowpass_hz: int,
) -> str:
    """Build a dialogue-keyed music ducking graph.

    The detector copy is band-limited to the speech range so low ambience and
    isolated rumbles are less likely to suppress the music.
    """
    return ";".join([
        (
            "[0:a:0]aresample=48000,"
            "aformat=sample_fmts=fltp:channel_layouts=stereo,"
            "asplit=2[foreground][detector]"
        ),
        (
            f"[detector]highpass=f={detector_highpass_hz},"
            f"lowpass=f={detector_lowpass_hz},"
            f"volume={number(key_boost_db)}dB[voice_key]"
        ),
        (
            f"[1:a:0]atrim=duration={number(duration)},asetpts=PTS-STARTPTS,"
            "aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"volume={number(music_volume_db)}dB[music_bed]"
        ),
        (
            "[music_bed][voice_key]sidechaincompress="
            f"threshold={number(threshold)}:ratio={number(ratio)}:"
            f"attack={number(attack_ms)}:release={number(release_ms)}:"
            "knee=3:makeup=1:detection=rms:link=average[ducked_music]"
        ),
        (
            "[foreground][ducked_music]"
            "amix=inputs=2:duration=first:dropout_transition=0:normalize=0,"
            "alimiter=limit=0.95:attack=5:release=50:level=false:latency=true[mixed]"
        ),
    ])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", "-i", type=Path, required=True, help="Input video with dialogue")
    parser.add_argument("--music", "-m", type=Path, required=True, help="Background music file")
    parser.add_argument("--output", "-o", type=Path, required=True, help="Output MP4 path")
    parser.add_argument(
        "--music-start",
        type=float,
        default=0.0,
        help="Music start offset in seconds (default: 0)",
    )
    parser.add_argument(
        "--music-volume-db",
        type=float,
        default=-8.0,
        help="Music gain before ducking, in dB (default: -8)",
    )
    parser.add_argument(
        "--key-boost-db",
        type=float,
        default=6.0,
        help="Gain applied only to the speech detector (default: 6)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.025,
        help="Linear sidechain threshold, 0.000976563-1 (default: 0.025)",
    )
    parser.add_argument("--ratio", type=float, default=8.0, help="Ducking ratio, 1-20 (default: 8)")
    parser.add_argument("--attack-ms", type=float, default=35.0, help="Ducking attack in ms")
    parser.add_argument("--release-ms", type=float, default=500.0, help="Music recovery in ms")
    parser.add_argument("--detector-highpass-hz", type=int, default=120)
    parser.add_argument("--detector-lowpass-hz", type=int, default=5000)
    parser.add_argument("--audio-bitrate", default="192k", help="AAC output bitrate")
    parser.add_argument("--force", action="store_true", help="Replace an existing output file")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print the FFmpeg command")
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> tuple[Path, Path, Path, dict[str, Any]]:
    input_video = resolve_path(args.input)
    music = resolve_path(args.music)
    output = resolve_path(args.output)

    for label, path in (("Input video", input_video), ("Music", music)):
        if not path.is_file():
            raise BackgroundMusicError(f"{label} does not exist: {path}")
    if output in {input_video, music}:
        raise BackgroundMusicError("Output must be different from both input files")
    if output.exists() and not args.force:
        raise BackgroundMusicError(f"Output already exists; pass --force to replace it: {output}")
    if args.music_start < 0:
        raise BackgroundMusicError("--music-start cannot be negative")
    if not -60 <= args.music_volume_db <= 12:
        raise BackgroundMusicError("--music-volume-db must be between -60 and 12")
    if not -24 <= args.key_boost_db <= 24:
        raise BackgroundMusicError("--key-boost-db must be between -24 and 24")
    if not 0.000976563 <= args.threshold <= 1:
        raise BackgroundMusicError("--threshold must be between 0.000976563 and 1")
    if not 1 <= args.ratio <= 20:
        raise BackgroundMusicError("--ratio must be between 1 and 20")
    if args.detector_highpass_hz >= args.detector_lowpass_hz:
        raise BackgroundMusicError("Detector high-pass frequency must be below low-pass frequency")

    input_info = probe(input_video)
    music_info = probe(music)
    if not has_stream(input_info, "video") or not has_stream(input_info, "audio"):
        raise BackgroundMusicError("Input video must contain both video and audio streams")
    if not has_stream(music_info, "audio"):
        raise BackgroundMusicError("Music file has no audio stream")
    return input_video, music, output, input_info


def mix(args: argparse.Namespace) -> None:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise BackgroundMusicError("ffmpeg and ffprobe are required on PATH")

    input_video, music, output, input_info = validate_args(args)
    duration = input_info["duration"]
    filter_complex = build_filter(
        duration=duration,
        music_volume_db=args.music_volume_db,
        key_boost_db=args.key_boost_db,
        threshold=args.threshold,
        ratio=args.ratio,
        attack_ms=args.attack_ms,
        release_ms=args.release_ms,
        detector_highpass_hz=args.detector_highpass_hz,
        detector_lowpass_hz=args.detector_lowpass_hz,
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    print(f"Input video: {input_video}")
    print(f"Music: {music} (start {args.music_start:.3f}s)")
    print(f"Duration: {duration:.3f}s")
    print(f"Music bed: {args.music_volume_db:.1f} dB")
    print(
        "Ducking: "
        f"threshold={args.threshold:g}, ratio={args.ratio:g}:1, "
        f"attack={args.attack_ms:g}ms, release={args.release_ms:g}ms"
    )
    print(f"Output: {output}")

    with tempfile.TemporaryDirectory(prefix="background-music-", dir=output.parent) as temp_dir:
        partial = Path(temp_dir) / "mixed.partial.mp4"
        command = [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-i",
            str(input_video),
            "-stream_loop",
            "-1",
            "-ss",
            number(args.music_start),
            "-i",
            str(music),
            "-filter_complex",
            filter_complex,
            "-map",
            "0:v:0",
            "-map",
            "[mixed]",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            args.audio_bitrate,
            "-ar",
            "48000",
            "-ac",
            "2",
            "-movflags",
            "+faststart",
            "-t",
            number(duration),
            str(partial),
        ]
        if args.dry_run:
            print("FFmpeg command:")
            print(" ".join(shlex.quote(part) for part in command))
            return

        run(command)
        output_info = probe(partial)
        if not has_stream(output_info, "video") or not has_stream(output_info, "audio"):
            raise BackgroundMusicError("Rendered output is missing a video or audio stream")
        if abs(output_info["duration"] - duration) > 0.12:
            raise BackgroundMusicError(
                f"Output duration changed unexpectedly: {output_info['duration']:.3f}s vs {duration:.3f}s"
            )
        if output.exists():
            output.unlink()
        partial.replace(output)

    print(f"Mixed background music successfully: {output}")


def main() -> int:
    try:
        mix(parse_args())
    except BackgroundMusicError as exc:
        print(f"Error: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

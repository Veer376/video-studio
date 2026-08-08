"""
Stage 3 of render pipeline: Mux the rendered video with the narration audio into
the final MP4 output file.

Usage:
    python3 render_final.py --project-dir library/2026-08-01_krishna-motivation
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


class FFmpegError(RuntimeError):
    pass


def run_ffmpeg(*args: str) -> None:
    cmd = ["ffmpeg", "-y"] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        tail = (result.stderr or result.stdout)[-4000:]
        raise FFmpegError(f"ffmpeg failed:\n{tail}")


def get_duration(path: Path) -> float:
    """Get media duration in seconds using ffprobe."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", str(path)],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return 0.0
    data = json.loads(result.stdout)
    return float(data.get("format", {}).get("duration", 0.0))


CLOSING_FADE_DURATION = 4.0   # total duration of audio fade-out


def main():
    parser = argparse.ArgumentParser(description="Mux video and narration audio into final MP4")
    parser.add_argument("--project-dir", required=True, help="Path to the project directory")
    parser.add_argument("--force", action="store_true", help="Re-render even if final video exists")
    args = parser.parse_args()

    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        print("ERROR: ffmpeg/ffprobe not found in PATH. Install ffmpeg first.", file=sys.stderr)
        sys.exit(1)

    project_dir = Path(args.project_dir)
    video_path = project_dir / "temp" / "video-no-audio.mp4"
    audio_path = project_dir / "audio" / "narration.wav"
    session_path = project_dir / "session.json"
    out_path = project_dir / "output" / "final-video.mp4"

    for p in [video_path, audio_path, session_path]:
        if not p.exists():
            print(f"ERROR: Required file not found: {p}", file=sys.stderr)
            sys.exit(1)

    if out_path.exists() and not args.force:
        print(f"✓ final-video.mp4 already exists. Use --force to re-render.")
        sys.exit(0)

    # If final-video.mp4 already exists, generate a versioned output filename (e.g. final-video-001.mp4) for easy comparison
    if out_path.exists():
        idx = 1
        while True:
            candidate = project_dir / "output" / f"final-video-{idx:03d}.mp4"
            if not candidate.exists():
                out_path = candidate
                break
            idx += 1

    out_path.parent.mkdir(parents=True, exist_ok=True)

    video_dur = get_duration(video_path)
    audio_dur = get_duration(audio_path)
    print(f"→ Muxing video ({video_dur:.2f}s) + audio ({audio_dur:.2f}s)")

    if video_dur + 0.75 < audio_dur:
        print(
            f"ERROR: Video stream is shorter than audio by {audio_dur - video_dur:.2f}s. "
            "Re-run timestamp alignment/render before muxing.",
            file=sys.stderr,
        )
        sys.exit(1)

    fade_st = max(0.0, video_dur - CLOSING_FADE_DURATION)
    audio_filter = f"apad,afade=t=out:st={fade_st:.3f}:d={CLOSING_FADE_DURATION:.3f}"

    # Mux: video copy without re-encode, audio padded & faded over final tail
    run_ffmpeg(
        "-i", str(video_path),
        "-i", str(audio_path),
        "-map", "0:v:0",     # video from video_path
        "-map", "1:a:0",     # audio from narration.wav
        "-c:v", "copy",      # no re-encode — subtitles are already burned
        "-c:a", "aac",
        "-b:a", "192k",
        "-af", audio_filter,
        "-t", f"{video_dur:.3f}",
        "-movflags", "+faststart",
        str(out_path),
    )

    final_dur = get_duration(out_path)
    size_mb = out_path.stat().st_size / (1024 * 1024)

    # Update session.json status
    if session_path.exists():
        session = json.loads(session_path.read_text(encoding="utf-8"))
        session["session"]["status"] = "render_complete"
        session_path.write_text(json.dumps(session, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"✓ Final video written: {out_path}")
    print(f"  Duration: {final_dur:.2f}s | Size: {size_mb:.1f} MB")
    print(f"  Status updated: render_complete")


if __name__ == "__main__":
    main()

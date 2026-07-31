from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import ffmpeg
from .audio import create_placeholder_audio, estimate_placeholder_duration, measure_scene_audio, pace_narration_audio, prepare_narration_audio
from .images import create_placeholder_image
from .manifest import load_manifest, save_manifest, validate_assets
from .renderer import prepare_dirs, render_video


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="story-video")
    parser.add_argument("command", choices=["validate", "prepare", "voice", "pace", "render", "build"])
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--placeholder-assets", action="store_true", help="Create deterministic local placeholders for missing images/audio.")
    parser.add_argument("--voice-model", help="Override manifest voice.model for this run.")
    parser.add_argument("--voice-name", help="Override manifest voice.voice for this run.")
    args = parser.parse_args(argv)

    try:
        manifest = load_manifest(args.manifest)
        if args.voice_model:
            manifest.voice.model = args.voice_model
        if args.voice_name:
            manifest.voice.voice = args.voice_name
        base_dir = args.manifest.resolve().parent
        if args.command == "validate":
            ffmpeg.require_tools()
            errors = validate_assets(manifest, base_dir)
            if errors:
                for error in errors:
                    print(error, file=sys.stderr)
                return 2
            print("Manifest and assets are valid.")
            return 0
        if args.command == "prepare":
            prepare_dirs(base_dir)
            if args.placeholder_assets:
                create_placeholders(manifest, base_dir, args.force)
                measure_scene_audio(manifest, base_dir)
                save_manifest(manifest)
            report_missing(manifest, base_dir)
            return 0
        if args.command == "voice":
            prepare_dirs(base_dir)
            prepare_narration_audio(manifest, base_dir, args.force)
            measure_scene_audio(manifest, base_dir)
            save_manifest(manifest)
            print("Narration audio is ready.")
            return 0
        if args.command == "pace":
            prepare_dirs(base_dir)
            pace_narration_audio(manifest, base_dir, args.force)
            save_manifest(manifest)
            print("Narration audio has been paced.")
            return 0
        if args.command == "render":
            measure_scene_audio(manifest, base_dir)
            save_manifest(manifest)
            out_path = render_video(manifest, base_dir, force=args.force)
            print(out_path)
            return 0
        if args.command == "build":
            prepare_dirs(base_dir)
            if args.placeholder_assets:
                create_placeholders(manifest, base_dir, args.force)
            elif manifest.voice.provider != "existing_audio":
                prepare_narration_audio(manifest, base_dir, args.force)
            measure_scene_audio(manifest, base_dir)
            save_manifest(manifest)
            asset_errors = validate_assets(manifest, base_dir)
            if asset_errors:
                for error in asset_errors:
                    print(error, file=sys.stderr)
                return 2
            out_path = render_video(manifest, base_dir, force=args.force)
            print(out_path)
            return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


def create_placeholders(manifest, base_dir: Path, force: bool) -> None:
    width, height = manifest.project.width_height
    for index, scene in enumerate(manifest.scenes, start=1):
        if scene.image_path:
            create_placeholder_image(base_dir / scene.image_path, f"{index}. {scene.id}", (width, height), force=force)
        if scene.audio_path:
            create_placeholder_audio(base_dir / scene.audio_path, estimate_placeholder_duration(scene.narration), force=force)


def report_missing(manifest, base_dir: Path) -> None:
    missing = validate_assets(manifest, base_dir)
    if not missing:
        print("All required assets are present.")
        return
    print("Missing assets:")
    for line in missing:
        print(f"- {line}")


if __name__ == "__main__":
    raise SystemExit(main())

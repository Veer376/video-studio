#!/usr/bin/env python3
"""Inspect, format, and copy resolved scene prompts for Gemini API, Flow, or subagent briefs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from .video.base import (
        PROJECT_ROOT,
        compile_scene,
        format_character_brief,
        load_characters,
        load_json,
        resolve_characters_path,
        resolve_path,
    )
except ImportError:
    from video.base import (
        PROJECT_ROOT,
        compile_scene,
        format_character_brief,
        load_characters,
        load_json,
        resolve_characters_path,
        resolve_path,
    )


DEFAULT_CONFIG = PROJECT_ROOT / "stories" / "chhotu-motu-rocket-tractor" / "scenes.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resolve and format scene prompts with character references."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="Path to scenes.json",
    )
    parser.add_argument(
        "--scene",
        action="append",
        default=[],
        help="Scene ID to inspect (can be repeated); default shows all",
    )
    parser.add_argument(
        "--part",
        action="append",
        default=[],
        help="Part ID to filter scenes",
    )
    parser.add_argument(
        "--format",
        choices=("gemini", "flow", "annotated", "brief", "all"),
        default="all",
        help="Output format: gemini (with <IMAGE_REF_N>), flow (with ref paths), annotated (with inline profiles), brief (subagent CHARACTER PROFILES: block), all (default)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config_path = resolve_path(PROJECT_ROOT, args.config)
    config = load_json(config_path)
    scenes = config.get("scenes", [])

    characters_file = config.get("characters_file", "characters.json")
    story_chars_path = resolve_characters_path(config_path, characters_file, PROJECT_ROOT)
    characters = load_characters(PROJECT_ROOT, story_chars_path)

    selected = [
        s for s in scenes
        if (not args.scene or s.get("id") in args.scene)
        and (not args.part or s.get("part_id") in args.part)
    ]

    if not selected:
        print("No matching scenes found.")
        sys.exit(1)

    for scene in selected:
        scene_id = scene.get("id", "unknown")
        subjects = scene.get("subjects", [])
        compiled = compile_scene(scene, characters, PROJECT_ROOT)

        print(f"\n{'='*70}")
        print(f"SCENE: {scene_id}  |  Part: {scene.get('part_id', '')}  |  Subjects: {subjects}")
        print(f"{'='*70}")

        if args.format in {"annotated", "all"}:
            print("\n[PROMPT WITH INLINE PROFILES]:")
            print(compiled.annotated_prompt)

        if args.format in {"gemini", "all"}:
            print("\n[GEMINI COMPILED PROMPT (<IMAGE_REF_N>)]:")
            print(compiled.prompt)
            print("\n  Reference Images in Order:")
            for idx, img in enumerate(compiled.images):
                print(f"    [{idx}] {img}")

        if args.format in {"flow", "all"}:
            print("\n[FLOW PROMPT & COMMAND]:")
            # For Flow, we can keep the raw prompt with @handles or compiled prompt
            ref_args = " ".join(f'--ref-file "{img}"' for img in compiled.images)
            cmd = f'python3 -m scripts.video --provider flow --prompt "{compiled.raw_prompt}" {ref_args} -o ./videos/{scene_id}.mp4'
            print(f"  Prompt : {compiled.raw_prompt}")
            print(f"  Command: {cmd}")

        if args.format in {"brief", "all"}:
            print("\n[SUBAGENT BRIEF - CHARACTER PROFILES]:")
            print(format_character_brief(subjects, characters, include_description=True))

    print(f"\n{'='*70}\n")


if __name__ == "__main__":
    main()

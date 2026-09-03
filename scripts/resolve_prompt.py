#!/usr/bin/env python3
"""Inspect, format, and copy resolved scene prompts for Gemini API, Flow, or subagent briefs."""

from __future__ import annotations

import argparse
import shlex
import sys
from pathlib import Path

try:
    from .video.base import (
        PROJECT_ROOT,
        compile_scene,
        format_character_brief,
        format_location_brief,
        load_characters,
        load_locations,
        load_json,
        resolve_characters_path,
        resolve_locations_path,
        resolve_path,
    )
    from .video.flow import prepare_scene_input
except ImportError:
    from video.base import (
        PROJECT_ROOT,
        compile_scene,
        format_character_brief,
        format_location_brief,
        load_characters,
        load_locations,
        load_json,
        resolve_characters_path,
        resolve_locations_path,
        resolve_path,
    )
    from video.flow import prepare_scene_input


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

    locations_file = config.get("locations_file")
    locations = {}
    if isinstance(locations_file, str):
        story_locations_path = resolve_locations_path(
            config_path, locations_file, PROJECT_ROOT
        )
        locations = load_locations(PROJECT_ROOT, story_locations_path)

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
        scene_locations = scene.get("locations", [])
        compiled = compile_scene(
            scene, characters, PROJECT_ROOT, locations=locations
        )

        print(f"\n{'='*70}")
        print(
            f"SCENE: {scene_id}  |  Part: {scene.get('part_id', '')}  |  "
            f"Subjects: {subjects}  |  Locations: {scene_locations}"
        )
        print(f"{'='*70}")

        if args.format in {"annotated", "all"}:
            print("\n[RESOLVED FLOW AUTHORING PROMPT - PROFILES DEFINED ONCE]:")
            print(compiled.annotated_prompt)

        if args.format in {"gemini", "all"}:
            print("\n[GEMINI COMPILED PROMPT (<IMAGE_REF_N>)]:")
            print(compiled.prompt)
            print("\n  Reference Images in Order:")
            for idx, img in enumerate(compiled.images):
                print(f"    [{idx}] {img}")

        if args.format in {"flow", "all"}:
            flow_input = prepare_scene_input(compiled, None)
            print("\n[FLOW PRODUCTION PROMPT]:")
            ref_args = " ".join(
                f"--ref-file {shlex.quote(str(img))}" for img in flow_input.images
            )
            cmd = (
                "python3 -m scripts.video --provider flow "
                f"--prompt {shlex.quote(flow_input.prompt)} {ref_args} "
                f"-o ./videos/{scene_id}.mp4"
            )
            print(f"  Prompt : {flow_input.prompt}")
            print(f"  Command: {cmd}")

        if args.format in {"brief", "all"}:
            print("\n[SUBAGENT BRIEF - CHARACTER PROFILES]:")
            print(format_character_brief(subjects, characters, include_description=True))
            print("\n[SUBAGENT BRIEF - LOCATION PROFILES]:")
            print(
                format_location_brief(
                    scene_locations, locations, include_description=True
                )
            )

    print(f"\n{'='*70}\n")


if __name__ == "__main__":
    main()

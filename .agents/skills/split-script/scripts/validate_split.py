#!/usr/bin/env python3
"""Validate a lossless semantic scene skeleton against script.md."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


AUDIO_TAG = re.compile(r"\[[^\]\n]+\]")
LEADING_QUOTE_MARKER = re.compile(r"(?m)^\s*>\s?")
SCENE_ID = re.compile(r"scene-(\d{3,})$")
TOP_LEVEL_KEYS = {"project_name", "total_words", "scene_count", "scenes"}
SCENE_KEYS = {"id", "text"}


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def strip_control_markers(text: str) -> str:
    return normalize_whitespace(LEADING_QUOTE_MARKER.sub("", AUDIO_TAG.sub("", text)))


def quote_state_tokens(text: str) -> list[tuple[str, bool]]:
    """Return narration tokens paired with their source quote-marker state."""
    tokens: list[tuple[str, bool]] = []
    for raw_line in text.splitlines():
        line = AUDIO_TAG.sub("", raw_line).strip()
        if not line:
            continue
        quoted = line.startswith(">")
        if quoted:
            line = re.sub(r"^>\s?", "", line)
        tokens.extend((token, quoted) for token in line.split())
    return tokens


def extract_narration(script_text: str) -> str:
    lines = script_text.splitlines()
    try:
        separator = next(index for index, line in enumerate(lines) if line.strip() == "---")
    except StopIteration as exc:
        raise ValueError("script.md is missing the required --- narration separator") from exc

    body_lines: list[str] = []
    for raw_line in lines[separator + 1 :]:
        line = AUDIO_TAG.sub("", raw_line).strip()
        if not line or line.startswith("#"):
            continue
        body_lines.append(line)
    narration = "\n".join(body_lines)
    if not strip_control_markers(narration):
        raise ValueError("script.md has no narration after the separator")
    return narration


def validate(script_path: Path, scenes_path: Path) -> list[str]:
    errors: list[str] = []
    try:
        source_raw = extract_narration(script_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [str(exc)]

    try:
        data = json.loads(scenes_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot read scenes manifest: {exc}"]

    if not isinstance(data, dict):
        return ["scenes manifest must be a JSON object"]

    extra_top = sorted(set(data) - TOP_LEVEL_KEYS)
    missing_top = sorted(TOP_LEVEL_KEYS - set(data))
    if extra_top:
        errors.append(f"unexpected top-level fields: {', '.join(extra_top)}")
    if missing_top:
        errors.append(f"missing top-level fields: {', '.join(missing_top)}")

    scenes = data.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        errors.append("scenes must be a non-empty array")
        return errors

    combined: list[str] = []
    for index, scene in enumerate(scenes, start=1):
        label = f"scene {index}"
        if not isinstance(scene, dict):
            errors.append(f"{label} must be an object")
            continue
        extra = sorted(set(scene) - SCENE_KEYS)
        missing = sorted(SCENE_KEYS - set(scene))
        if extra:
            errors.append(f"{label} has unexpected fields: {', '.join(extra)}")
        if missing:
            errors.append(f"{label} is missing fields: {', '.join(missing)}")

        expected_id = f"scene-{index:03d}"
        scene_id = scene.get("id")
        if scene_id != expected_id or not isinstance(scene_id, str) or not SCENE_ID.fullmatch(scene_id):
            errors.append(f"{label} id must be {expected_id}")

        text = scene.get("text")
        if not isinstance(text, str) or not strip_control_markers(text):
            errors.append(f"{label} text must be a non-empty string")
            continue
        if AUDIO_TAG.search(text):
            errors.append(f"{expected_id} contains a bracketed performance direction")
        word_count = len(strip_control_markers(text).split())
        if len(scenes) > 1 and word_count < 3:
            errors.append(f"{expected_id} has {word_count} words; minimum is 3")
        combined.append(text)

    source = strip_control_markers(source_raw)
    reconstructed = strip_control_markers("\n".join(combined))
    if reconstructed != source:
        errors.append("scene texts do not reconstruct the narration exactly")
    if quote_state_tokens("\n".join(combined)) != quote_state_tokens(source_raw):
        errors.append("scene quote markers do not preserve the script's quoted and unquoted spans")

    expected_words = len(source.split())
    if data.get("total_words") != expected_words:
        errors.append(f"total_words must be {expected_words}")
    if data.get("scene_count") != len(scenes):
        errors.append(f"scene_count must be {len(scenes)}")
    if not isinstance(data.get("project_name"), str) or not data.get("project_name", "").strip():
        errors.append("project_name must be a non-empty string")
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path)
    parser.add_argument("--script-file", type=Path)
    parser.add_argument("--scenes-file", type=Path)
    args = parser.parse_args()
    if args.project_dir:
        args.script_file = args.script_file or args.project_dir / "script.md"
        args.scenes_file = args.scenes_file or args.project_dir / "scenes.json"
    if not args.script_file or not args.scenes_file:
        parser.error("provide --project-dir or both --script-file and --scenes-file")
    return args


def main() -> int:
    args = parse_args()
    errors = validate(args.script_file, args.scenes_file)
    if errors:
        print("Split validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"Split validation passed: {args.scenes_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

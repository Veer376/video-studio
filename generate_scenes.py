"""Generate one canonical Omni Flash video for each scene in scenes.json."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from main import create_client, generate_video


HANDLE_PATTERN = re.compile(r"(?<![A-Za-z0-9_])@[A-Za-z][A-Za-z0-9_-]*")


class ConfigError(ValueError):
    """Raised when project JSON cannot be compiled safely."""


@dataclass(frozen=True)
class CompiledScene:
    prompt: str
    images: list[Path]
    task: str
    handle_order: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("scenes.json"),
        help="Scene configuration file (default: scenes.json)",
    )
    parser.add_argument(
        "--scene",
        action="append",
        default=[],
        help="Generate only this scene ID; repeat to select multiple scenes",
    )
    parser.add_argument(
        "--part",
        action="append",
        default=[],
        help="Generate only this part ID; repeat to select multiple parts",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print work without calling Gemini or FFmpeg",
    )
    parser.add_argument(
        "--regenerate",
        action="store_true",
        help="Replace an existing scene video after its replacement passes validation",
    )
    parser.add_argument(
        "--backend",
        choices=("auto", "vertex", "developer"),
        default="auto",
    )
    parser.add_argument("--gcp-project", default=None)
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"Configuration file does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"Expected a JSON object in {path}")
    return data


def resolve_path(project_root: Path, configured_path: str) -> Path:
    path = Path(configured_path)
    return path if path.is_absolute() else project_root / path


def load_characters(path: Path, project_root: Path) -> dict[str, dict[str, Any]]:
    data = load_json(path)
    entries = data.get("characters")
    if not isinstance(entries, list):
        raise ConfigError(f"{path} must contain a characters array")

    characters: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ConfigError(f"Every character in {path} must be an object")
        handle = entry.get("handle")
        reference_path = entry.get("reference_path")
        if not isinstance(handle, str) or not HANDLE_PATTERN.fullmatch(handle):
            raise ConfigError(f"Invalid character handle: {handle!r}")
        if handle in characters:
            raise ConfigError(f"Duplicate character handle: {handle}")
        if not isinstance(reference_path, str) or not reference_path:
            raise ConfigError(f"Character {handle} has no reference_path")

        resolved_reference = resolve_path(project_root, reference_path)
        if not resolved_reference.is_file():
            raise ConfigError(
                f"Reference image for {handle} does not exist: {resolved_reference}"
            )
        characters[handle] = {**entry, "resolved_reference_path": resolved_reference}
    return characters


def scene_output_path(scene: dict[str, Any], project_root: Path) -> Path:
    configured = scene.get("output_path")
    if not isinstance(configured, str) or not configured:
        raise ConfigError(f"Scene {scene.get('id')!r} has no output_path")
    return resolve_path(project_root, configured)


def scene_first_frame_path(
    scene: dict[str, Any], project_root: Path
) -> Path | None:
    configured = scene.get("first_frame_path")
    if configured is None:
        return None
    if not isinstance(configured, str) or not configured:
        raise ConfigError(
            f"Scene {scene.get('id')!r} first_frame_path must be a non-empty path string"
        )
    path = resolve_path(project_root, configured)
    if not path.is_file():
        raise ConfigError(
            f"Curated first frame for scene {scene.get('id')!r} does not exist: {path}"
        )
    return path


def compile_scene(
    scene: dict[str, Any],
    characters: dict[str, dict[str, Any]],
    project_root: Path,
    first_frame: Path | None = None,
) -> CompiledScene:
    scene_id = scene.get("id")
    prompt = scene.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ConfigError(f"Scene {scene_id} is waiting for a non-empty prompt")

    subjects = scene.get("subjects", [])
    if not isinstance(subjects, list) or not all(isinstance(item, str) for item in subjects):
        raise ConfigError(f"Scene {scene_id} subjects must be an array of handles")
    if len(subjects) != len(set(subjects)):
        raise ConfigError(f"Scene {scene_id} contains duplicate subject handles")

    prompt_handles = set(HANDLE_PATTERN.findall(prompt))
    subject_handles = set(subjects)
    missing_from_prompt = subject_handles - prompt_handles
    missing_from_subjects = prompt_handles - subject_handles
    if missing_from_prompt:
        raise ConfigError(
            f"Scene {scene_id} subjects absent from prompt: {sorted(missing_from_prompt)}"
        )
    if missing_from_subjects:
        raise ConfigError(
            f"Scene {scene_id} prompt handles absent from subjects: {sorted(missing_from_subjects)}"
        )
    unknown = subject_handles - set(characters)
    if unknown:
        raise ConfigError(f"Scene {scene_id} uses unknown handles: {sorted(unknown)}")

    handle_order = sorted(subjects, key=prompt.index)
    images: list[Path] = []
    declarations: list[str] = []
    next_image_number = 1

    if first_frame is not None:
        if not first_frame.is_file():
            raise ConfigError(f"Continuity frame does not exist: {first_frame}")
        images.append(first_frame)
        declarations.append(f"[# Sources <FIRST_FRAME>@Image{next_image_number}]")
        next_image_number += 1
        if "<FIRST_FRAME>" not in prompt:
            prompt = f"<FIRST_FRAME> {prompt}"

    for reference_index, handle in enumerate(handle_order):
        token = f"<IMAGE_REF_{reference_index}>"
        prompt = prompt.replace(handle, token)
        images.append(characters[handle]["resolved_reference_path"])
        declarations.append(f"[# References {token}@Image{next_image_number}]")
        next_image_number += 1

    reference_images = scene.get("reference_images", [])
    if not isinstance(reference_images, list):
        raise ConfigError(f"Scene {scene_id} reference_images must be an array")
    for item in reference_images:
        if isinstance(item, str):
            configured_path = item
        elif isinstance(item, dict) and isinstance(item.get("path"), str):
            configured_path = item["path"]
        else:
            raise ConfigError(
                f"Scene {scene_id} reference_images entries must be paths or path objects"
            )
        path = resolve_path(project_root, configured_path)
        if not path.is_file():
            raise ConfigError(f"Scene {scene_id} reference image does not exist: {path}")
        reference_index = len(images) - (1 if first_frame is not None else 0)
        token = f"<IMAGE_REF_{reference_index}>"
        images.append(path)
        declarations.append(f"[# References {token}@Image{next_image_number}]")
        next_image_number += 1

    compiled_prompt = "\n".join([*declarations, prompt]) if declarations else prompt
    task = "reference_to_video" if images else "text_to_video"
    return CompiledScene(compiled_prompt, images, task, handle_order)


def verify_video(path: Path) -> None:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "stream=codec_type",
        "-of",
        "json",
        str(path),
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError("ffprobe is required to verify generated videos") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"ffprobe rejected {path}: {exc.stderr.strip()}") from exc

    stream_data = json.loads(result.stdout)
    stream_types = {stream.get("codec_type") for stream in stream_data.get("streams", [])}
    if not {"video", "audio"}.issubset(stream_types):
        raise RuntimeError(f"Expected video and audio streams in {path}; found {stream_types}")


def extract_last_frame(video: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-v",
        "error",
        "-y",
        "-sseof",
        "-1",
        "-i",
        str(video),
        "-an",
        "-vf",
        "reverse",
        "-frames:v",
        "1",
        str(destination),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError("FFmpeg is required for reference_scene_id continuity") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"Could not extract the final frame from {video}: {exc.stderr.strip()}"
        ) from exc


def scene_is_selected(scene: dict[str, Any], args: argparse.Namespace) -> bool:
    scene_selected = not args.scene or scene.get("id") in args.scene
    part_selected = not args.part or scene.get("part_id") in args.part
    return scene_selected and part_selected


def run(args: argparse.Namespace) -> int:
    config_path = args.config.resolve()
    project_root = config_path.parent
    config = load_json(config_path)
    scenes = config.get("scenes")
    if not isinstance(scenes, list) or not all(isinstance(item, dict) for item in scenes):
        raise ConfigError(f"{config_path} must contain a scenes array")

    scene_ids = [scene.get("id") for scene in scenes]
    if any(not isinstance(scene_id, str) or not scene_id for scene_id in scene_ids):
        raise ConfigError("Every scene must have a non-empty string id")
    if len(scene_ids) != len(set(scene_ids)):
        raise ConfigError("Scene IDs must be unique")
    unknown_requested = set(args.scene) - set(scene_ids)
    if unknown_requested:
        raise ConfigError(f"Unknown --scene IDs: {sorted(unknown_requested)}")

    characters_file = config.get("characters_file", "characters.json")
    if not isinstance(characters_file, str):
        raise ConfigError("characters_file must be a path string")
    characters = load_characters(resolve_path(project_root, characters_file), project_root)
    scenes_by_id = {scene["id"]: scene for scene in scenes}

    client = None
    generated_count = 0
    for scene in scenes:
        if not scene_is_selected(scene, args):
            continue

        scene_id = scene["id"]
        output_path = scene_output_path(scene, project_root)
        if output_path.is_file() and not args.regenerate:
            verify_video(output_path)
            print(f"KEEP {scene_id}: {output_path}")
            continue

        reference_scene_id = scene.get("reference_scene_id")
        reference_video: Path | None = None
        if reference_scene_id is not None:
            if reference_scene_id not in scenes_by_id:
                raise ConfigError(
                    f"Scene {scene_id} references unknown scene {reference_scene_id!r}"
                )
            reference_video = scene_output_path(
                scenes_by_id[reference_scene_id], project_root
            )
            if not reference_video.is_file():
                print(f"BLOCKED {scene_id}: missing {reference_video}")
                continue
            verify_video(reference_video)

        curated_first_frame = scene_first_frame_path(scene, project_root)
        preflight_first_frame = curated_first_frame or reference_video

        try:
            preflight = compile_scene(
                scene, characters, project_root, first_frame=preflight_first_frame
            )
        except ConfigError as exc:
            print(f"WAIT {scene_id}: {exc}")
            continue

        action = "REPLACE" if output_path.is_file() else "CREATE"
        print(
            f"PLAN {scene_id}: {action} {output_path}, "
            f"{len(preflight.images)} image input(s), task={preflight.task}, "
            f"handles={preflight.handle_order}"
        )
        if args.dry_run:
            continue

        if client is None:
            client, backend_label = create_client(args.backend, args.gcp_project)
            print(f"Using {backend_label}")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        partial_path = output_path.with_suffix(".partial.mp4")
        try:
            with tempfile.TemporaryDirectory(prefix=f"{scene_id}-continuity-") as temp_dir:
                first_frame: Path | None = None
                if curated_first_frame is not None:
                    first_frame = curated_first_frame
                elif reference_video is not None:
                    first_frame = Path(temp_dir) / f"{reference_scene_id}_last_frame.png"
                    extract_last_frame(reference_video, first_frame)
                compiled = compile_scene(
                    scene, characters, project_root, first_frame=first_frame
                )
                byte_count = generate_video(
                    client=client,
                    prompt=compiled.prompt,
                    output=partial_path,
                    images=compiled.images,
                    task=compiled.task,
                    aspect_ratio=config.get("aspect_ratio", "16:9"),
                    model=config.get("model", "gemini-omni-flash-preview"),
                )
            verify_video(partial_path)
            os.replace(partial_path, output_path)
        except Exception as exc:
            partial_path.unlink(missing_ok=True)
            raise RuntimeError(f"Generation failed for {scene_id}: {exc}") from exc

        generated_count += 1
        print(f"SAVED {scene_id}: {byte_count:,} bytes -> {output_path}")

    if args.dry_run:
        print("Dry run complete; Gemini was not called.")
    else:
        print(f"Generation complete: {generated_count} scene(s).")
    return 0


def main() -> None:
    args = parse_args()
    try:
        raise SystemExit(run(args))
    except (ConfigError, RuntimeError) as exc:
        raise SystemExit(f"Error: {exc}") from exc


if __name__ == "__main__":
    main()

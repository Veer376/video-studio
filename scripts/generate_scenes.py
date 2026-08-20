"""Generate reviewed Omni Flash attempt candidates and promote selected attempts."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from .review_contract import (
        MAX_ATTEMPTS,
        ReviewContractError,
        attempt_path,
        project_relative,
        review_path,
        sha256_file,
        validate_canonical_binding,
        validate_review,
        write_review_atomic,
    )
    from .video import (
        BaseProvider,
        CharacterEntry,
        CompiledScene,
        ConfigError,
        HANDLE_PATTERN,
        PROJECT_ROOT,
        VideoError,
        compile_scene,
        generate_video,
        get_provider,
        load_characters,
        load_json,
        resolve_characters_path,
        resolve_path,
    )
    from .video.google import create_client
except ImportError:  # Direct execution: python3 scripts/generate_scenes.py
    from review_contract import (
        MAX_ATTEMPTS,
        ReviewContractError,
        attempt_path,
        project_relative,
        review_path,
        sha256_file,
        validate_canonical_binding,
        validate_review,
        write_review_atomic,
    )
    from video import (
        BaseProvider,
        CharacterEntry,
        CompiledScene,
        ConfigError,
        HANDLE_PATTERN,
        PROJECT_ROOT,
        VideoError,
        compile_scene,
        generate_video,
        get_provider,
        load_characters,
        load_json,
        resolve_characters_path,
        resolve_path,
    )
    from video.google import create_client


DEFAULT_CONFIG = PROJECT_ROOT / "stories" / "aloo-flood-rescue" / "scenes.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="Story scene configuration (default: current flood story)",
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
        help="Generate even when a canonical video or this attempt candidate exists",
    )
    parser.add_argument(
        "--attempt",
        type=int,
        default=1,
        help=f"Attempt number from 1 to {MAX_ATTEMPTS} (default: 1)",
    )
    parser.add_argument(
        "--promote-attempt",
        type=int,
        default=None,
        help="Promote this reviewed attempt to the canonical scene path",
    )
    parser.add_argument(
        "--backend",
        choices=("auto", "vertex", "developer"),
        default="auto",
    )
    parser.add_argument("--gcp-project", default=None)
    parser.add_argument(
        "--provider",
        choices=("google", "flow"),
        default="google",
        help="Video generation provider: google or flow (default: google)",
    )
    parser.add_argument(
        "--flow-host",
        default="127.0.0.1:8001",
        help="Flow agent server host:port (default: 127.0.0.1:8001)",
    )
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


def scene_attempt_path(config_path: Path, scene_id: str, attempt: int) -> Path:
    try:
        return attempt_path(config_path, scene_id, attempt)
    except ReviewContractError as exc:
        raise ConfigError(str(exc)) from exc


def validate_promotion_review(
    config_path: Path,
    scene_id: str,
    attempt: int,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    try:
        review, selected_candidate = validate_review(
            config_path, scene_id, project_root
        )
    except ReviewContractError as exc:
        raise ConfigError(str(exc)) from exc
    if review["selected_attempt"] != attempt:
        raise ConfigError(
            f"Review for {scene_id} selects attempt "
            f"{review['selected_attempt']!r}, not {attempt}"
        )
    if selected_candidate != scene_attempt_path(config_path, scene_id, attempt):
        raise ConfigError(f"Review for {scene_id} selects a mismatched candidate")
    return review


def promote_attempt(
    config_path: Path,
    scene: dict[str, Any],
    attempt: int,
    project_root: Path,
) -> tuple[Path, Path]:
    scene_id = scene["id"]
    candidate = scene_attempt_path(config_path, scene_id, attempt)
    if not candidate.is_file():
        raise ConfigError(f"Attempt candidate does not exist: {candidate}")
    review = validate_promotion_review(config_path, scene_id, attempt, project_root)
    verify_video(candidate)

    canonical = scene_output_path(scene, project_root)
    canonical.parent.mkdir(parents=True, exist_ok=True)
    staged = canonical.with_suffix(".promoting.mp4")
    original_review = dict(review)
    try:
        shutil.copy2(candidate, staged)
        verify_video(staged)
        candidate_hash = sha256_file(candidate)
        if sha256_file(staged) != candidate_hash:
            raise RuntimeError("Staged canonical video differs from selected attempt")
        review["promoted_attempt"] = attempt
        review["canonical_path"] = project_relative(canonical, project_root)
        review["canonical_sha256"] = candidate_hash
        write_review_atomic(review_path(config_path, scene_id), review)
        os.replace(staged, canonical)
        validate_canonical_binding(review, canonical, project_root)
    except Exception:
        write_review_atomic(review_path(config_path, scene_id), original_review)
        raise
    finally:
        staged.unlink(missing_ok=True)
    return candidate, canonical


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
    if first_frame is not None and len(images) == 1:
        task = "image_to_video"
    else:
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
    config_path = args.config if args.config.is_absolute() else PROJECT_ROOT / args.config
    config_path = config_path.resolve()
    project_root = PROJECT_ROOT
    config = load_json(config_path)
    scenes = config.get("scenes")
    if not isinstance(scenes, list) or not all(isinstance(item, dict) for item in scenes):
        raise ConfigError(f"{config_path} must contain a scenes array")

    scene_ids = [scene.get("id") for scene in scenes]
    if any(not isinstance(scene_id, str) or not scene_id for scene_id in scene_ids):
        raise ConfigError("Every scene must have a non-empty string id")
    if len(scene_ids) != len(set(scene_ids)):
        raise ConfigError("Scene IDs must be unique")
    if not 1 <= args.attempt <= MAX_ATTEMPTS:
        raise ConfigError(f"--attempt must be between 1 and {MAX_ATTEMPTS}")
    if args.promote_attempt is not None and not 1 <= args.promote_attempt <= MAX_ATTEMPTS:
        raise ConfigError(
            f"--promote-attempt must be between 1 and {MAX_ATTEMPTS}"
        )
    if args.promote_attempt is not None and args.regenerate:
        raise ConfigError("--promote-attempt cannot be combined with --regenerate")
    unknown_requested = set(args.scene) - set(scene_ids)
    if unknown_requested:
        raise ConfigError(f"Unknown --scene IDs: {sorted(unknown_requested)}")

    scenes_by_id = {scene["id"]: scene for scene in scenes}

    selected_scenes = [scene for scene in scenes if scene_is_selected(scene, args)]
    if args.promote_attempt is not None:
        for scene in selected_scenes:
            scene_id = scene["id"]
            candidate = scene_attempt_path(config_path, scene_id, args.promote_attempt)
            canonical = scene_output_path(scene, project_root)
            if args.dry_run:
                validate_promotion_review(
                    config_path, scene_id, args.promote_attempt, project_root
                )
                if not candidate.is_file():
                    raise ConfigError(f"Attempt candidate does not exist: {candidate}")
                verify_video(candidate)
                print(f"PROMOTE {scene_id}: {candidate} -> {canonical}")
                continue
            source, destination = promote_attempt(
                config_path, scene, args.promote_attempt, project_root
            )
            print(f"PROMOTED {scene_id}: {source} -> {destination}")
        return 0

    characters_file = config.get("characters_file", "characters.json")
    if not isinstance(characters_file, str):
        raise ConfigError("characters_file must be a path string")
    story_chars_path = resolve_characters_path(config_path, characters_file, project_root)
    characters = load_characters(story_chars_path, project_root)

    client: Any = None
    provider_instance: BaseProvider | None = None
    generated_count = 0
    for scene in selected_scenes:

        scene_id = scene["id"]
        output_path = scene_output_path(scene, project_root)
        if output_path.is_file() and not args.regenerate:
            verify_video(output_path)
            print(f"KEEP {scene_id}: {output_path}")
            continue
        attempt_path = scene_attempt_path(config_path, scene_id, args.attempt)
        if attempt_path.is_file():
            if args.regenerate:
                raise ConfigError(
                    f"Attempt candidate already exists and is immutable: {attempt_path}. "
                    "Use the next attempt number."
                )
            verify_video(attempt_path)
            print(f"KEEP ATTEMPT {scene_id}: {attempt_path}")
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
            try:
                predecessor_review, _ = validate_review(
                    config_path, reference_scene_id, project_root
                )
                validate_canonical_binding(
                    predecessor_review, reference_video, project_root
                )
            except ReviewContractError as exc:
                raise ConfigError(
                    f"Scene {scene_id} predecessor {reference_scene_id} is not a "
                    f"reviewed promoted canonical: {exc}"
                ) from exc
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

        print(
            f"PLAN {scene_id}: ATTEMPT {args.attempt} -> {attempt_path}, "
            f"{len(preflight.images)} image input(s), task={preflight.task}, "
            f"handles={preflight.handle_order}"
        )
        if args.dry_run:
            continue

        provider = getattr(args, "provider", "google")
        flow_host = getattr(args, "flow_host", "127.0.0.1:8001")

        if client is None and provider_instance is None:
            if provider == "google":
                client, backend_label = create_client(args.backend, args.gcp_project)
                print(f"Using {backend_label}")
            else:
                provider_instance = get_provider("flow", host=flow_host)
                provider_instance.preflight()
                print(f"Using Google Flow ({flow_host})")

        attempt_path.parent.mkdir(parents=True, exist_ok=True)
        partial_path = attempt_path.with_suffix(".partial.mp4")
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
                scene_duration = scene.get("duration", config.get("duration", 10))
                if provider == "google":
                    byte_count = generate_video(
                        client=client,
                        prompt=compiled.prompt,
                        output=partial_path,
                        images=compiled.images,
                        task=compiled.task,
                        aspect_ratio=config.get("aspect_ratio", "16:9"),
                        duration=scene_duration,
                        model=config.get("model", "gemini-omni-flash-preview"),
                    )
                else:
                    byte_count = generate_video(
                        prompt=compiled.raw_prompt,
                        output=partial_path,
                        images=compiled.images,
                        task=compiled.task,
                        aspect_ratio=config.get("aspect_ratio", "16:9"),
                        duration=scene_duration,
                        model=config.get("model", "gemini-omni-flash-preview"),
                        provider_instance=provider_instance,
                    )
            verify_video(partial_path)
            os.replace(partial_path, attempt_path)
        except Exception as exc:
            partial_path.unlink(missing_ok=True)
            raise RuntimeError(f"Generation failed for {scene_id}: {exc}") from exc

        generated_count += 1
        print(f"SAVED ATTEMPT {scene_id}: {byte_count:,} bytes -> {attempt_path}")

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

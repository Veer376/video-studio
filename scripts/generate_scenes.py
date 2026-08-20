#!/usr/bin/env python3
"""Generate active scene videos and archive rejected versions beside them."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

try:
    from .review_contract import (
        MAX_GENERATIONS,
        ReviewContractError,
        active_contact_sheet_path,
        archived_path,
        begin_active_review,
        load_review,
        project_relative,
        review_path,
        validate_active_bytes,
        validate_canonical_binding,
        validate_review,
        write_review_atomic,
    )
    from .video import (
        BaseProvider,
        ConfigError,
        PROJECT_ROOT,
        compile_scene,
        generate_video,
        get_provider,
        load_characters,
        load_json,
        resolve_characters_path,
        resolve_path,
    )
    from .video.flow import prepare_scene_input, requires_google_fallback
    from .video.google import create_client
except ImportError:  # Direct execution: python3 scripts/generate_scenes.py
    from review_contract import (
        MAX_GENERATIONS,
        ReviewContractError,
        active_contact_sheet_path,
        archived_path,
        begin_active_review,
        load_review,
        project_relative,
        review_path,
        validate_active_bytes,
        validate_canonical_binding,
        validate_review,
        write_review_atomic,
    )
    from video import (
        BaseProvider,
        ConfigError,
        PROJECT_ROOT,
        compile_scene,
        generate_video,
        get_provider,
        load_characters,
        load_json,
        resolve_characters_path,
        resolve_path,
    )
    from video.flow import prepare_scene_input, requires_google_fallback
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
        help="Archive the reviewed active video and generate its replacement",
    )
    parser.add_argument(
        "--restore",
        choices=("a1", "a2"),
        default=None,
        help="Restore an archived video as the active scene for fresh review",
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


def scene_output_path(scene: dict[str, Any], project_root: Path) -> Path:
    configured = scene.get("output_path")
    if not isinstance(configured, str) or not configured:
        raise ConfigError(f"Scene {scene.get('id')!r} has no output_path")
    return resolve_path(project_root, configured)


def existing_archive_numbers(active: Path) -> list[int]:
    return [
        number
        for number in range(1, MAX_GENERATIONS + 1)
        if archived_path(active, number).is_file()
    ]


def review_snapshot(
    review: dict[str, Any],
    archived_video: Path,
    archived_sheet: Path | None,
    project_root: Path,
) -> dict[str, Any]:
    if "attempts" in review:
        selected = review["selected_attempt"]
        item = review["attempts"][selected - 1]
        return {
            "video_path": project_relative(archived_video, project_root),
            "video_sha256": review.get("canonical_sha256"),
            "contact_sheet_path": item.get("contact_sheet_path"),
            "media_valid": item.get("media_valid"),
            "decision": review.get("decision"),
            "findings": item.get("findings", []),
            "diagnosis": item.get("diagnosis"),
            "repair_applied": item.get("repair_applied"),
        }
    snapshot = {
        key: review.get(key)
        for key in (
            "video_path",
            "video_sha256",
            "contact_sheet_path",
            "media_valid",
            "decision",
            "findings",
            "diagnosis",
            "repair_applied",
        )
    }
    snapshot["video_path"] = project_relative(archived_video, project_root)
    if archived_sheet is not None:
        snapshot["contact_sheet_path"] = project_relative(
            archived_sheet, project_root
        )
    return snapshot


def archive_active_video(
    config_path: Path,
    scene: dict[str, Any],
    project_root: Path,
) -> tuple[int, Path, list[dict[str, Any]]]:
    scene_id = scene["id"]
    active = scene_output_path(scene, project_root)
    review = load_review(config_path, scene_id)
    validate_active_bytes(review, active, project_root)
    archives = existing_archive_numbers(active)
    expected = list(range(1, len(archives) + 1))
    if archives != expected:
        raise ConfigError(f"Scene {scene_id} has non-sequential video archives")
    number = len(archives) + 1
    if number > MAX_GENERATIONS:
        raise ConfigError(f"Scene {scene_id} already has {MAX_GENERATIONS} archives")
    destination = archived_path(active, number)
    active_sheet = active_contact_sheet_path(config_path, scene_id)
    archived_sheet = archived_path(active_sheet, number)
    current_sheet: Path | None = None
    if "attempts" not in review:
        configured_sheet = review.get("contact_sheet_path")
        if not isinstance(configured_sheet, str) or (
            resolve_path(project_root, configured_sheet).resolve()
            != active_sheet.resolve()
            or not active_sheet.is_file()
        ):
            raise ConfigError(f"Scene {scene_id} has no active contact sheet to archive")
        if archived_sheet.exists():
            raise ConfigError(f"Archive evidence already exists: {archived_sheet}")
        current_sheet = active_sheet
    history = review.get("history", []) if "attempts" not in review else []
    if not isinstance(history, list):
        raise ConfigError(f"Scene {scene_id} review history is invalid")
    history = list(history)
    original_review = json.loads(json.dumps(review))
    try:
        os.replace(active, destination)
        if current_sheet is not None:
            os.replace(current_sheet, archived_sheet)
        history.append(
            review_snapshot(
                review,
                destination,
                archived_sheet if current_sheet is not None else None,
                project_root,
            )
        )
        waiting = number == MAX_GENERATIONS
        state = {
            "scene_id": scene_id,
            "decision": "await_user" if waiting else "pending_generation",
            "video_path": None,
            "video_sha256": None,
            "contact_sheet_path": None,
            "media_valid": None,
            "findings": [],
            "diagnosis": None,
            "repair_applied": None,
            "history": history,
            "next_action": "await_user" if waiting else "generate",
        }
        write_review_atomic(review_path(config_path, scene_id), state)
    except Exception:
        if destination.is_file() and not active.exists():
            os.replace(destination, active)
        if current_sheet is not None and archived_sheet.is_file():
            os.replace(archived_sheet, current_sheet)
        write_review_atomic(review_path(config_path, scene_id), original_review)
        raise
    return number, destination, history


def restore_archived_video(
    config_path: Path,
    scene: dict[str, Any],
    archive_number: int,
    project_root: Path,
) -> tuple[Path, Path]:
    scene_id = scene["id"]
    active = scene_output_path(scene, project_root)
    source = archived_path(active, archive_number)
    if active.exists():
        raise ConfigError(f"Active scene video already exists: {active}")
    if not source.is_file():
        raise ConfigError(f"Archived scene video does not exist: {source}")
    review = load_review(config_path, scene_id)
    history = review.get("history", [])
    if not isinstance(history, list):
        raise ConfigError(f"Scene {scene_id} review history is invalid")
    archived_sheet = archived_path(
        active_contact_sheet_path(config_path, scene_id), archive_number
    )
    active_sheet = active_contact_sheet_path(config_path, scene_id)
    shutil.copy2(source, active)
    try:
        if archived_sheet.is_file():
            active_sheet.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(archived_sheet, active_sheet)
        begin_active_review(config_path, scene_id, active, project_root, history)
    except Exception:
        active.unlink(missing_ok=True)
        active_sheet.unlink(missing_ok=True)
        raise
    return source, active


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
    if args.restore is not None and args.regenerate:
        raise ConfigError("--restore cannot be combined with --regenerate")
    unknown_requested = set(args.scene) - set(scene_ids)
    if unknown_requested:
        raise ConfigError(f"Unknown --scene IDs: {sorted(unknown_requested)}")

    scenes_by_id = {scene["id"]: scene for scene in scenes}

    selected_scenes = [scene for scene in scenes if scene_is_selected(scene, args)]
    if args.restore is not None:
        if len(selected_scenes) != 1:
            raise ConfigError("--restore requires exactly one selected --scene")
        scene = selected_scenes[0]
        number = int(args.restore[1:])
        active = scene_output_path(scene, project_root)
        source = archived_path(active, number)
        if args.dry_run:
            if active.exists():
                raise ConfigError(f"Active scene video already exists: {active}")
            if not source.is_file():
                raise ConfigError(f"Archived scene video does not exist: {source}")
            print(f"RESTORE {scene['id']}: {source} -> {active}")
            return 0
        source, destination = restore_archived_video(
            config_path, scene, number, project_root
        )
        print(
            f"RESTORED {scene['id']}: {source} -> {destination}. "
            "Review the active video before continuing."
        )
        return 0

    characters_file = config.get("characters_file", "characters.json")
    if not isinstance(characters_file, str):
        raise ConfigError("characters_file must be a path string")
    story_chars_path = resolve_characters_path(config_path, characters_file, project_root)
    characters = load_characters(story_chars_path, project_root)

    provider = getattr(args, "provider", "google")
    flow_host = getattr(args, "flow_host", "127.0.0.1:8001")
    client: Any = None
    provider_instance: BaseProvider | None = None
    generated_count = 0
    for scene in selected_scenes:

        scene_id = scene["id"]
        output_path = scene_output_path(scene, project_root)
        archives = existing_archive_numbers(output_path)
        history: list[dict[str, Any]] = []
        generation_number = len(archives) + 1

        if output_path.is_file():
            try:
                review = load_review(config_path, scene_id)
            except ReviewContractError as exc:
                print(f"WAIT {scene_id}: {exc}")
                continue
            decision = review.get("decision")
            if decision == "pending_review":
                print(f"WAIT {scene_id}: review the active video -> {output_path}")
                continue
            if decision != "needs_fix" and not args.regenerate:
                try:
                    validate_review(config_path, scene_id, project_root)
                    validate_canonical_binding(review, output_path, project_root)
                except ReviewContractError as exc:
                    print(f"WAIT {scene_id}: {exc}")
                    continue
                verify_video(output_path)
                print(f"KEEP {scene_id}: accepted active video -> {output_path}")
                continue

            next_archive = len(archives) + 1
            if next_archive > MAX_GENERATIONS:
                print(
                    f"STOP {scene_id}: the active video cannot be archived because "
                    f"{MAX_GENERATIONS} archives already exist. Ask the user what to keep."
                )
                continue
            if args.dry_run:
                destination = archived_path(output_path, next_archive)
                print(f"ARCHIVE {scene_id}: {output_path} -> {destination}")
                if next_archive == MAX_GENERATIONS:
                    print(
                        f"STOP {scene_id}: both generated videos need fixing. "
                        "Ask the user what to keep."
                    )
                    continue
                history = review.get("history", [])
                generation_number = next_archive + 1
            else:
                archived_number, destination, history = archive_active_video(
                    config_path, scene, project_root
                )
                print(f"ARCHIVED {scene_id}: {output_path} -> {destination}")
                if archived_number == MAX_GENERATIONS:
                    print(
                        f"STOP {scene_id}: both generated videos need fixing. "
                        "Ask the user to select an archive or revise the scene manually."
                    )
                    continue
                generation_number = archived_number + 1
        elif archives:
            try:
                review = load_review(config_path, scene_id)
            except ReviewContractError as exc:
                print(f"WAIT {scene_id}: {exc}")
                continue
            if len(archives) >= MAX_GENERATIONS or review.get("decision") == "await_user":
                print(
                    f"STOP {scene_id}: no active video; archived versions are "
                    f"{[archived_path(output_path, n).name for n in archives]}. "
                    "Ask the user what to restore."
                )
                continue
            if review.get("decision") != "pending_generation":
                print(f"WAIT {scene_id}: review state does not permit replacement generation")
                continue
            stored_history = review.get("history", [])
            if not isinstance(stored_history, list):
                raise ConfigError(f"Scene {scene_id} review history is invalid")
            history = stored_history
            generation_number = len(archives) + 1

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
                    f"accepted active video: {exc}"
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

        planned_provider = provider
        if provider == "flow" and requires_google_fallback(
            preflight, preflight_first_frame
        ):
            planned_provider = "google (Flow fallback: start frame + references)"

        print(
            f"PLAN {scene_id}: generation {generation_number} -> {output_path}, "
            f"{len(preflight.images)} image input(s), task={preflight.task}, "
            f"handles={preflight.handle_order}, provider={planned_provider}"
        )
        if args.dry_run:
            continue

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
                scene_duration = scene.get("duration", config.get("duration", 10))
                fallback_to_google = provider == "flow" and requires_google_fallback(
                    compiled, first_frame
                )
                if fallback_to_google:
                    reference_count = len(compiled.images) - 1
                    print(
                        f"ROUTE {scene_id}: Flow -> Google because the literal start "
                        f"frame must be combined with {reference_count} required "
                        "reference image(s)."
                    )

                if provider == "google" or fallback_to_google:
                    if client is None:
                        client, backend_label = create_client(
                            gcp_project=args.gcp_project
                        )
                        print(f"Using {backend_label}")
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
                    if provider_instance is None:
                        provider_instance = get_provider("flow", host=flow_host)
                        provider_instance.preflight()
                        print(f"Using Google Flow ({flow_host})")
                    flow_input = prepare_scene_input(compiled, first_frame)
                    byte_count = generate_video(
                        prompt=flow_input.prompt,
                        output=partial_path,
                        images=flow_input.images,
                        task=compiled.task,
                        aspect_ratio=config.get("aspect_ratio", "16:9"),
                        duration=scene_duration,
                        model=config.get("model", "gemini-omni-flash-preview"),
                        start_frame=flow_input.start_frame,
                        provider_instance=provider_instance,
                    )
            verify_video(partial_path)
            os.replace(partial_path, output_path)
        except Exception as exc:
            partial_path.unlink(missing_ok=True)
            raise RuntimeError(f"Generation failed for {scene_id}: {exc}") from exc

        generated_count += 1
        begin_active_review(config_path, scene_id, output_path, project_root, history)
        print(
            f"ACTIVE {scene_id}: {byte_count:,} bytes -> {output_path}. "
            "Review this video before generating a dependent scene or rendering."
        )

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

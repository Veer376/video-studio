"""Provider-neutral character and scene illustration orchestration."""
import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from studio.core.config import load_production_config
from studio.core.paths import is_root_asset_locator, resolve_asset_locator
from studio.images.providers import cloudflare, flow, google

IMAGE_WIDTH = 1920
IMAGE_HEIGHT = 1080
MAX_REFERENCE_IMAGES = 4


@dataclass(frozen=True)
class ReferenceImage:
    path: Path
    role: str


@dataclass(frozen=True)
class CharacterTask:
    key: str
    output_path: Path
    source_path: Path | None


def load_env():
    from studio.core.env import load_env as load_configured_env
    load_configured_env()


def is_valid_image(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        with Image.open(path) as image:
            image.verify()
        return True
    except (OSError, ValueError):
        return False


def ensure_character_image_paths(characters: dict) -> bool:
    changed = False
    for key, character in characters.items():
        if not isinstance(character, dict):
            raise ValueError(f"character {key!r} must be an object")
        image_path = character.get("image_path")
        if image_path is None or not str(image_path).strip():
            character["image_path"] = f"assets/characters/{key}.png"
            changed = True
        elif not isinstance(image_path, str):
            raise ValueError(f"character {key!r}.image_path must be a string")
    return changed


def character_asset_path(project_dir: Path, key: str, character: dict) -> Path:
    image_path = str(character.get("image_path") or "").strip()
    if not image_path:
        raise ValueError(f"character {key!r} has no image_path")
    candidate = resolve_asset_locator(project_dir, image_path)
    if is_root_asset_locator(image_path):
        return candidate
    local_character_root = (project_dir / "assets" / "characters").resolve()
    if not candidate.is_relative_to(local_character_root):
        raise ValueError(
            f"character {key!r}.image_path must be under assets/characters: {image_path!r}"
        )
    return candidate


def local_character_asset_path(project_dir: Path, key: str) -> Path:
    return (project_dir / "assets" / "characters" / f"{key}.png").resolve()


def character_prompt(character_key: str, character: dict) -> str | None:
    value = character.get("prompt")
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"character {character_key!r}.prompt must be a string or null")
    return value.strip()


def build_character_prompt(character_key: str, character: dict, style_prompt: str) -> str:
    canonical = str(character.get("canonical_name") or character_key).strip()
    description = character_prompt(character_key, character)
    if description is None:
        raise ValueError(f"character {character_key!r} has no generation prompt")
    return (
        f"{style_prompt} — Canonical identity reference for {canonical}: {description} — "
        "show this subject alone, with the complete identifying silhouette visible, in a "
        "neutral pose or natural resting state against a simple unobtrusive background, "
        "even readable lighting, no narrative action, no text, no additional characters"
    )


def plan_character_tasks(
    project_dir: Path,
    characters: dict,
    *,
    force: bool,
) -> list[CharacterTask]:
    tasks: list[CharacterTask] = []
    for key, character in characters.items():
        source_or_output = character_asset_path(project_dir, key, character)
        locator = str(character["image_path"]).strip()
        description = character_prompt(key, character)

        if is_root_asset_locator(locator):
            if not is_valid_image(source_or_output):
                raise ValueError(
                    f"shared root asset is missing or invalid for {key!r}: {source_or_output}"
                )
            if description is None:
                continue
            local_output = local_character_asset_path(project_dir, key)
            if is_valid_image(local_output) and not force:
                character["image_path"] = f"assets/characters/{key}.png"
                continue
            tasks.append(CharacterTask(key, local_output, source_or_output))
            continue

        if is_valid_image(source_or_output):
            if force and description is not None:
                tasks.append(CharacterTask(key, source_or_output, None))
            continue
        if description is None:
            raise ValueError(
                f"character {key!r} has neither a valid image nor a generation prompt"
            )
        tasks.append(CharacterTask(key, source_or_output, None))
    return tasks


def scene_reference_id(scene: dict) -> str | None:
    ref_scene_id = scene.get("reference_scene_id")
    if ref_scene_id:
        return str(ref_scene_id)
    legacy = scene.get("reference_scene_ids") or []
    return str(legacy[0]) if legacy else None


def strip_duplicated_style(image_prompt: str, style_prompt: str) -> str:
    """Remove a legacy style prefix because production adds it exactly once."""
    prompt = image_prompt.strip()
    for separator in (" — ", ", ", " - ", ": "):
        prefix = f"{style_prompt.strip()}{separator}"
        if prompt.startswith(prefix):
            return prompt[len(prefix):].strip()
    return prompt


def resolve_style_prompt(session: dict, scenes_data: dict) -> str:
    """Load the approved session design, with read-only legacy compatibility."""
    visual = session.get("visual") or {}
    if not isinstance(visual, dict):
        raise ValueError("session.visual must be an object")

    style_prompt = visual.get("style_prompt")
    if style_prompt is not None:
        style_id = visual.get("style_id")
        if not isinstance(style_id, str) or not style_id.strip():
            raise ValueError("session.visual.style_id is required with style_prompt")
        if not isinstance(style_prompt, str) or not style_prompt.strip():
            raise ValueError("session.visual.style_prompt must be a non-empty string")
        return style_prompt.strip()

    legacy_style = visual.get("style")
    if isinstance(legacy_style, dict):
        legacy_style = legacy_style.get("style")
    if not isinstance(legacy_style, str) or not legacy_style.strip():
        legacy_style = scenes_data.get("visual_style")
        if isinstance(legacy_style, dict):
            legacy_style = legacy_style.get("style")
    if isinstance(legacy_style, str) and legacy_style.strip():
        return legacy_style.strip()

    raise ValueError(
        "approved visual design is missing; run orchestrate-visuals before illustration"
    )


def assemble_scene_prompt(scene: dict, characters: dict, style_prompt: str) -> str:
    raw_prompt = scene.get("image_prompt")
    if not isinstance(raw_prompt, str) or not raw_prompt.strip():
        raise ValueError(f"{scene.get('id', '<unknown>')}.image_prompt is missing")

    image_prompt = strip_duplicated_style(raw_prompt, style_prompt)
    full_prompt = f"{style_prompt} — {image_prompt}"
    ref_chars = scene.get("referenced_characters") or scene.get("characters") or []
    if not isinstance(ref_chars, list):
        raise ValueError(f"{scene.get('id', '<unknown>')}.referenced_characters must be a list")

    for char_key in ref_chars:
        char_info = characters.get(char_key)
        if not isinstance(char_info, dict):
            raise ValueError(
                f"{scene.get('id', '<unknown>')} references undefined character {char_key!r}"
            )
        char_desc = character_prompt(str(char_key), char_info)
        canonical = str(char_info.get("canonical_name") or char_key)
        if char_desc:
            full_prompt += f" — {canonical}: {char_desc}"
    return full_prompt


def rank_scene_characters(scene: dict, characters: dict) -> list[str]:
    referenced = scene.get("referenced_characters") or scene.get("characters") or []
    if not isinstance(referenced, list):
        raise ValueError(f"{scene.get('id', '<unknown>')}.referenced_characters must be a list")

    prompt = str(scene.get("image_prompt") or "").casefold()

    def rank(item: tuple[int, str]) -> tuple[int, int, int]:
        order, key = item
        character = characters.get(key)
        if not isinstance(character, dict):
            raise ValueError(
                f"{scene.get('id', '<unknown>')} references undefined character {key!r}"
            )
        terms = {
            str(key).replace("_", " ").casefold(),
            str(character.get("canonical_name") or "").strip().casefold(),
        }
        positions = [prompt.find(term) for term in terms if term and prompt.find(term) >= 0]
        if positions:
            return (0, min(positions), order)
        return (1, order, order)

    indexed: list[tuple[int, str]] = []
    seen: set[str] = set()
    for index, key in enumerate(referenced):
        normalized = str(key)
        if normalized not in seen:
            indexed.append((index, normalized))
            seen.add(normalized)
    return [key for _, key in sorted(indexed, key=rank)]


def scene_reference_images(
    project_dir: Path,
    scene: dict,
    characters: dict,
) -> list[ReferenceImage]:
    references: list[ReferenceImage] = []
    ref_scene_id = scene_reference_id(scene)
    if ref_scene_id:
        ref_path = project_dir / "images" / f"{ref_scene_id}.png"
        if not is_valid_image(ref_path):
            raise ValueError(
                f"{scene.get('id', '<unknown>')} continuity image is missing or invalid: "
                f"{ref_path}"
            )
        references.append(
            ReferenceImage(ref_path, f"previous scene {ref_scene_id} for visual continuity")
        )

    ranked_characters = rank_scene_characters(scene, characters)
    selected_count = MAX_REFERENCE_IMAGES - len(references)
    selected = ranked_characters[:selected_count]
    omitted = ranked_characters[selected_count:]
    missing_fallback = [
        key for key in omitted if character_prompt(key, characters[key]) is None
    ]
    if missing_fallback:
        raise ValueError(
            f"{scene.get('id', '<unknown>')} exceeds the reference budget; add prompt "
            f"fallbacks for: {', '.join(missing_fallback)}"
        )

    for key in selected:
        if len(references) >= MAX_REFERENCE_IMAGES:
            break
        character = characters[key]
        path = character_asset_path(project_dir, key, character)
        if not is_valid_image(path):
            raise ValueError(
                f"canonical character image is missing or invalid for {key!r}: {path}"
            )
        canonical = str(character.get("canonical_name") or key)
        references.append(ReferenceImage(path, f"canonical appearance of {canonical}"))
    return references


def validate_reference_graph(scenes: list[dict]) -> dict[str, dict]:
    scene_by_id: dict[str, dict] = {}
    positions: dict[str, int] = {}
    for index, scene in enumerate(scenes):
        scene_id = scene.get("id")
        if not isinstance(scene_id, str) or not scene_id:
            raise ValueError(f"scene at index {index} has no valid id")
        if scene_id in scene_by_id:
            raise ValueError(f"duplicate scene id: {scene_id}")
        scene_by_id[scene_id] = scene
        positions[scene_id] = index

    for scene_id, scene in scene_by_id.items():
        ref_scene_id = scene_reference_id(scene)
        if not ref_scene_id:
            continue
        if ref_scene_id not in scene_by_id:
            raise ValueError(f"{scene_id} references missing scene {ref_scene_id}")
        if positions[ref_scene_id] >= positions[scene_id]:
            raise ValueError(f"{scene_id} must reference an earlier scene, got {ref_scene_id}")
    return scene_by_id


def main():
    parser = argparse.ArgumentParser(description="Generate canonical characters and scene images")
    parser.add_argument("--project-dir", required=True, help="Path to the project directory")
    parser.add_argument("--force", action="store_true", help="Re-generate even if image already exists")
    parser.add_argument(
        "--provider",
        choices=("cloudflare", "flow", "google"),
        help="Override configured image provider",
    )
    parser.add_argument("--model", help="Override configured image model")
    parser.add_argument("--concurrency", type=int, default=2, help="Number of parallel generation threads")
    parser.add_argument(
        "--phase",
        choices=("all", "characters", "scenes"),
        default="all",
        help="Run both phases, canonical character assets only, or scene images only",
    )
    args = parser.parse_args()
    if args.concurrency < 1:
        parser.error("--concurrency must be at least 1")

    load_env()
    credentials = cloudflare.load_credentials()
    credentials_reported = False
    google_client = None
    flow_ready = False

    def require_provider() -> None:
        nonlocal credentials_reported, google_client, flow_ready
        if provider_name == "cloudflare":
            if not credentials:
                raise RuntimeError(
                    "No Cloudflare ACCOUNT_ID / API_TOKEN credentials found in "
                    "an explicit STUDIO_ENV_FILE"
                )
            if not credentials_reported:
                print(f"  Loaded {len(credentials)} Cloudflare account credential pair(s).")
                credentials_reported = True
        elif provider_name == "flow":
            if not flow_ready:
                flow.require_ready()
                flow_ready = True
        elif google_client is None:
            google_client = google.create_client()

    project_dir = Path(args.project_dir)
    session_path = project_dir / "session.json"
    scenes_path = project_dir / "scenes.json"

    if not session_path.exists():
        print(f"ERROR: session.json not found at {session_path}", file=sys.stderr)
        sys.exit(1)
    if not scenes_path.exists():
        print(f"ERROR: scenes.json not found at {scenes_path}", file=sys.stderr)
        sys.exit(1)

    session = json.loads(session_path.read_text(encoding="utf-8"))
    scenes_data = json.loads(scenes_path.read_text(encoding="utf-8"))

    try:
        production = load_production_config(
            session,
            provider=args.provider,
            model=args.model,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    provider_name = production.image_provider
    model_name = production.image_model
    if provider_name == "cloudflare":
        model_name = cloudflare.normalize_model(model_name)
    elif provider_name == "flow":
        try:
            model_name = flow.normalize_model(model_name)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        try:
            model_name = google.normalize_model(model_name)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            sys.exit(1)

    aspect_ratio = session.get("visual", {}).get("aspect_ratio", "16:9")
    if aspect_ratio == "9:16":
        width, height = 1080, 1920
    else:
        width, height = IMAGE_WIDTH, IMAGE_HEIGHT

    try:
        style_prompt = resolve_style_prompt(session, scenes_data)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"→ Illustration phase: {args.phase} (Resolution: {width}x{height})")
    print(f"  Provider: {provider_name}")
    print(f"  Model: {model_name}")
    print(f"  Global Design: {style_prompt}")

    def generate_with_provider(
        *,
        prompt: str,
        out_path: Path,
        reference_images: list[ReferenceImage],
    ) -> None:
        if provider_name == "cloudflare":
            cloudflare.generate_image(
                credentials=credentials,
                model=model_name,
                prompt=prompt,
                width=width,
                height=height,
                out_path=out_path,
                reference_images=reference_images,
            )
            return
        if provider_name == "flow":
            flow.generate_image(
                model=model_name,
                prompt=prompt,
                aspect_ratio=aspect_ratio,
                out_path=out_path,
                reference_images=reference_images,
            )
            return
        if google_client is None:
            raise RuntimeError("Google image provider was not initialized")
        google.generate_image(
            client=google_client,
            model=model_name,
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            out_path=out_path,
            reference_images=reference_images,
        )

    # Validate and prepare prompts before spending any generation credits.
    scenes = scenes_data.get("scenes", [])
    characters = scenes_data.get("characters", {})
    if not isinstance(scenes, list) or not scenes:
        print("ERROR: scenes.json has no scenes", file=sys.stderr)
        sys.exit(1)
    if not isinstance(characters, dict):
        print("ERROR: scenes.json characters must be an object", file=sys.stderr)
        sys.exit(1)

    try:
        ensure_character_image_paths(characters)
        for key, character in characters.items():
            character_asset_path(project_dir, key, character)
            character_prompt(key, character)
        scene_by_id = validate_reference_graph(scenes)
        prompts = {
            scene["id"]: assemble_scene_prompt(scene, characters, style_prompt)
            for scene in scenes
        }
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    # Persist deterministic asset paths before generation so interrupted runs resume cleanly.
    scenes_path.write_text(json.dumps(scenes_data, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.phase in ("all", "characters"):
        try:
            character_tasks = plan_character_tasks(
                project_dir,
                characters,
                force=args.force,
            )
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            sys.exit(1)
        character_failures: set[str] = set()
        if character_tasks:
            try:
                require_provider()
            except RuntimeError as exc:
                print(f"ERROR: {exc}", file=sys.stderr)
                sys.exit(1)
            print(
                f"→ Generating {len(character_tasks)} canonical character asset(s) "
                f"(max workers: {args.concurrency})"
            )

            def character_worker(task: CharacterTask) -> bool:
                character = characters[task.key]
                print(f"  → Generating character asset: {task.key} (model: {model_name})")
                try:
                    references = (
                        [
                            ReferenceImage(
                                task.source_path,
                                f"source identity of {character.get('canonical_name') or task.key}",
                            )
                        ]
                        if task.source_path
                        else []
                    )
                    generate_with_provider(
                        prompt=build_character_prompt(task.key, character, style_prompt),
                        out_path=task.output_path,
                        reference_images=references,
                    )
                    return True
                except Exception as exc:
                    print(
                        f"✗ Failed to generate character {task.key}: {exc}",
                        file=sys.stderr,
                    )
                    return False

            with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as executor:
                futures = {
                    executor.submit(character_worker, task): task
                    for task in character_tasks
                }
                for future in as_completed(futures):
                    task = futures[future]
                    if future.result():
                        characters[task.key]["image_path"] = (
                            f"assets/characters/{task.key}.png"
                        )
                    else:
                        character_failures.add(task.key)
        else:
            print("✓ All canonical character assets already exist.")

        if character_failures:
            print(
                f"ERROR: Character generation incomplete: {', '.join(sorted(character_failures))}",
                file=sys.stderr,
            )
            sys.exit(1)
        scenes_path.write_text(
            json.dumps(scenes_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        if args.phase == "characters":
            print("✓ Canonical character phase complete.")
            return

    try:
        pending_adaptations = [
            key
            for key, character in characters.items()
            if is_root_asset_locator(str(character.get("image_path") or "").strip())
            and character_prompt(key, character) is not None
        ]
        missing_character_assets = [
            key
            for key, character in characters.items()
            if not is_valid_image(character_asset_path(project_dir, key, character))
        ]
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    if pending_adaptations:
        print(
            "ERROR: Scene phase requires root character adaptation first: "
            + ", ".join(sorted(pending_adaptations)),
            file=sys.stderr,
        )
        sys.exit(1)
    if missing_character_assets:
        print(
            "ERROR: Scene phase requires canonical character assets first: "
            + ", ".join(sorted(missing_character_assets)),
            file=sys.stderr,
        )
        sys.exit(1)

    pending: set[str] = set()
    for scene in scenes:
        scene_id = scene["id"]
        out_path = project_dir / "images" / f"{scene_id}.png"
        if is_valid_image(out_path) and not args.force:
            scene["image_path"] = f"images/{scene_id}.png"
            continue
        pending.add(scene_id)

    generation_failures: set[str] = set()
    if not pending:
        print("✓ All images already exist. Nothing to generate.")
    else:
        try:
            require_provider()
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            sys.exit(1)
        print(
            f"→ Generating {len(pending)} images with dependency-aware concurrency "
            f"(max workers: {args.concurrency})"
        )
        succeeded: set[str] = set()
        failed = generation_failures

        def worker(scene_id: str) -> bool:
            scene = scene_by_id[scene_id]
            out_path = project_dir / "images" / f"{scene_id}.png"
            ref_scene_id = scene_reference_id(scene)
            try:
                references = scene_reference_images(project_dir, scene, characters)
                if references:
                    mapping = ", ".join(reference.role for reference in references)
                    print(f"  {scene_id}: {mapping} (model: {model_name})")
                else:
                    print(f"  {scene_id}: generating image (model: {model_name})")
                generate_with_provider(
                    prompt=prompts[scene_id],
                    out_path=out_path,
                    reference_images=references,
                )
                scene["image_path"] = f"images/{scene_id}.png"
                return True
            except Exception as e:
                print(f"✗ Failed to generate image for {scene_id}: {e}", file=sys.stderr)
                return False

        while pending:
            blocked_by_failure = {
                scene_id
                for scene_id in pending
                if scene_reference_id(scene_by_id[scene_id]) in failed
            }
            for scene_id in sorted(blocked_by_failure):
                ref_scene_id = scene_reference_id(scene_by_id[scene_id])
                print(
                    f"✗ Skipping {scene_id}: reference scene {ref_scene_id} failed",
                    file=sys.stderr,
                )
            pending -= blocked_by_failure
            failed |= blocked_by_failure
            if not pending:
                break

            ready = [
                scene_id
                for scene_id in pending
                if not scene_reference_id(scene_by_id[scene_id])
                or scene_reference_id(scene_by_id[scene_id]) not in pending
            ]
            if not ready:
                failed |= pending
                print(
                    f"ERROR: unresolved scene reference dependencies: {', '.join(sorted(pending))}",
                    file=sys.stderr,
                )
                pending.clear()
                break

            with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as executor:
                futures = {executor.submit(worker, scene_id): scene_id for scene_id in ready}
                for future in as_completed(futures):
                    scene_id = futures[future]
                    if future.result():
                        succeeded.add(scene_id)
                    else:
                        failed.add(scene_id)
            pending -= set(ready)

        print(
            f"→ Generation complete: {len(succeeded)}/{len(succeeded) + len(failed)} succeeded."
        )

    # Write updated scenes.json manifest
    scenes_path.write_text(json.dumps(scenes_data, indent=2, ensure_ascii=False), encoding="utf-8")
    
    # Update session status only when every scene has a concrete image on disk.
    missing = [
        s["id"]
        for s in scenes
        if not is_valid_image(project_dir / "images" / f"{s['id']}.png")
    ]
    incomplete = sorted(set(missing) | generation_failures)
    if scenes and not incomplete:
        session["session"]["status"] = "illustrate_complete"
        session_path.write_text(json.dumps(session, indent=2, ensure_ascii=False), encoding="utf-8")
        print("✓ session.json status updated to: illustrate_complete")
    else:
        print(
            f"ERROR: Illustration incomplete after generation: {', '.join(incomplete)}",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()

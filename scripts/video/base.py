"""Core base classes, two-tier character registry loader, and prompt compilation for video generation."""

from __future__ import annotations

import abc
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
HANDLE_PATTERN = re.compile(r"(?<![A-Za-z0-9_])@[A-Za-z][A-Za-z0-9_-]*")


class VideoError(RuntimeError):
    """Base exception for video generation failures."""


class ConfigError(ValueError):
    """Raised when project or scene configuration cannot be compiled safely."""


class ProviderUnavailableError(VideoError):
    """Raised when a video generation provider is unreachable or unconfigured."""


class CreditError(VideoError):
    """Raised when an account lacks sufficient credits for generation."""


@dataclass(frozen=True)
class CharacterEntry:
    handle: str
    name: str
    reference_path: str
    resolved_reference_path: Path
    profile: str = ""
    description: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CompiledScene:
    prompt: str
    images: list[Path]
    task: str
    handle_order: list[str]
    raw_prompt: str = ""
    annotated_prompt: str = ""


def resolve_path(project_root: Path, configured_path: str | Path) -> Path:
    path = Path(configured_path)
    return path if path.is_absolute() else project_root / path


def resolve_characters_path(config_path: Path, characters_file: str | Path, project_root: Path = PROJECT_ROOT) -> Path:
    """Resolve character file path whether specified as project-relative or story-relative."""
    direct = resolve_path(project_root, characters_file)
    if direct.is_file():
        return direct
    relative = config_path.parent / characters_file
    if relative.is_file():
        return relative
    return direct


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


def _load_character_entries(
    path: Path, project_root: Path
) -> dict[str, CharacterEntry]:
    """Parse character array from one JSON file into CharacterEntry objects."""
    if not path.is_file():
        return {}

    data = load_json(path)
    entries = data.get("characters")
    if entries is None:
        return {}
    if not isinstance(entries, list):
        raise ConfigError(f"{path} must contain a characters array")

    result: dict[str, CharacterEntry] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ConfigError(f"Every character in {path} must be an object")
        handle = entry.get("handle")
        name = entry.get("name", handle)
        reference_path = entry.get("reference_path")
        profile = entry.get("profile", "")
        description = entry.get("description", "")

        if not isinstance(handle, str) or not HANDLE_PATTERN.fullmatch(handle):
            raise ConfigError(f"Invalid character handle: {handle!r} in {path}")
        if not isinstance(reference_path, str) or not reference_path:
            raise ConfigError(f"Character {handle} in {path} has no reference_path")

        resolved_reference = resolve_path(project_root, reference_path)
        if not resolved_reference.is_file():
            raise ConfigError(
                f"Reference image for {handle} does not exist: {resolved_reference}"
            )

        extra = {k: v for k, v in entry.items() if k not in {"handle", "name", "reference_path", "profile", "description"}}

        result[handle] = CharacterEntry(
            handle=handle,
            name=name if isinstance(name, str) else handle,
            reference_path=reference_path,
            resolved_reference_path=resolved_reference,
            profile=profile if isinstance(profile, str) else "",
            description=description if isinstance(description, str) else "",
            extra=extra,
        )
    return result


def load_characters(
    path_or_root: Path = PROJECT_ROOT,
    story_or_root: Path | str | None = None,
) -> dict[str, CharacterEntry]:
    """Load and merge two-tier character registry.
    
    Supports both signatures:
    - load_characters(project_root, story_characters_path)
    - load_characters(story_characters_path, project_root)
    """
    if isinstance(path_or_root, Path) and path_or_root.is_file():
        story_characters_path = path_or_root
        project_root = story_or_root if isinstance(story_or_root, Path) and story_or_root.is_dir() else PROJECT_ROOT
    else:
        project_root = path_or_root if isinstance(path_or_root, Path) and path_or_root.is_dir() else PROJECT_ROOT
        story_characters_path = Path(story_or_root) if story_or_root else None

    global_path = project_root / "characters.json"
    characters = _load_character_entries(global_path, project_root) if global_path.is_file() else {}

    if story_characters_path is not None:
        story_path = resolve_path(project_root, story_characters_path)
        if story_path.is_file() and story_path != global_path:
            story_chars = _load_character_entries(story_path, project_root)
            # Story entries override or add to global registry
            for handle, entry in story_chars.items():
                if handle in characters:
                    # Inherit global profile/description if story entry left them empty
                    merged_profile = entry.profile or characters[handle].profile
                    merged_desc = entry.description or characters[handle].description
                    characters[handle] = CharacterEntry(
                        handle=handle,
                        name=entry.name or characters[handle].name,
                        reference_path=entry.reference_path,
                        resolved_reference_path=entry.resolved_reference_path,
                        profile=merged_profile,
                        description=merged_desc,
                        extra={**characters[handle].extra, **entry.extra},
                    )
                else:
                    characters[handle] = entry

    return characters


def compile_scene(
    scene: dict[str, Any],
    characters: dict[str, CharacterEntry],
    project_root: Path = PROJECT_ROOT,
    first_frame: Path | None = None,
) -> CompiledScene:
    """Compile a scene configuration into model prompt tokens, ordered image references, and tasks."""
    scene_id = scene.get("id", "unknown")
    prompt = scene.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ConfigError(f"Scene {scene_id} is waiting for a non-empty prompt")

    raw_prompt = prompt
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

    # Preserve exact handle-token order from the prompt. Using str.index/replace
    # would corrupt prefixed handles such as @hero and @hero-alt.
    handle_order = list(dict.fromkeys(HANDLE_PATTERN.findall(prompt)))
    token_by_handle = {
        handle: f"<IMAGE_REF_{index}>"
        for index, handle in enumerate(handle_order)
    }
    images: list[Path] = []
    declarations: list[str] = []
    next_image_number = 1

    # Annotated prompt with profiles for inspection
    def annotate_handle(match: re.Match[str]) -> str:
        handle = match.group(0)
        char_entry = characters[handle]
        profile = getattr(char_entry, "profile", None) or (
            char_entry.get("profile") if isinstance(char_entry, dict) else ""
        )
        return f"{handle} ({profile})" if profile else handle

    annotated_prompt = HANDLE_PATTERN.sub(annotate_handle, raw_prompt)

    if first_frame is not None:
        if not first_frame.is_file():
            raise ConfigError(f"Continuity frame does not exist: {first_frame}")
        images.append(first_frame)
        declarations.append(f"[# Sources <FIRST_FRAME>@Image{next_image_number}]")
        next_image_number += 1
        if "<FIRST_FRAME>" not in prompt:
            prompt = f"<FIRST_FRAME> {prompt}"

    for reference_index, handle in enumerate(handle_order):
        token = token_by_handle[handle]
        char_entry = characters[handle]
        ref_path = getattr(char_entry, "resolved_reference_path", None) or (char_entry.get("resolved_reference_path") if isinstance(char_entry, dict) else None)
        if not isinstance(ref_path, Path):
            ref_path = Path(ref_path) if ref_path else None
        if ref_path is None or not ref_path.is_file():
            raise ConfigError(f"Resolved reference image for {handle} is missing or invalid: {ref_path}")
        images.append(ref_path)
        declarations.append(f"[# References {token}@Image{next_image_number}]")
        next_image_number += 1

    prompt = HANDLE_PATTERN.sub(
        lambda match: token_by_handle[match.group(0)], prompt
    )

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

    char_brief = format_character_brief(handle_order, characters)
    prompt_blocks = []
    if declarations:
        prompt_blocks.append("\n".join(declarations))
    if char_brief:
        prompt_blocks.append(char_brief)
    prompt_blocks.append(prompt)
    compiled_prompt = "\n\n".join(prompt_blocks)

    if first_frame is not None and len(images) == 1:
        task = "image_to_video"
    else:
        task = "reference_to_video" if images else "text_to_video"

    return CompiledScene(
        prompt=compiled_prompt,
        images=images,
        task=task,
        handle_order=handle_order,
        raw_prompt=raw_prompt,
        annotated_prompt=annotated_prompt,
    )


def format_character_brief(
    handles: Sequence[str],
    characters: dict[str, CharacterEntry],
    *,
    include_description: bool = False,
) -> str:
    """Format model-facing profiles, optionally with narrative context."""
    if not handles:
        return ""
    lines = ["CHARACTER MORPHOLOGY & PROFILES:"]
    for idx, handle in enumerate(handles):
        token = f"<IMAGE_REF_{idx}>"
        if handle in characters:
            c = characters[handle]
            lines.append(f"- {token} ({handle}, {c.name}):")
            if c.profile:
                lines.append(f"  {c.profile}")
            if include_description and c.description and c.description != c.profile:
                lines.append(f"  {c.description}")
        else:
            lines.append(f"- {token} ({handle}): [Unregistered character]")
    return "\n".join(lines)


class BaseProvider(abc.ABC):
    """Abstract base provider for video generation backends."""

    name: str = "base"

    @abc.abstractmethod
    def preflight(self) -> bool:
        """Check provider health, authentication, or connection."""

    @abc.abstractmethod
    def generate_video(
        self,
        *,
        prompt: str,
        output: Path,
        images: Sequence[Path] = (),
        videos: Sequence[Path] = (),
        task: str | None = None,
        aspect_ratio: str = "16:9",
        duration: int = 10,
        model: str | None = None,
        **kwargs: Any,
    ) -> int:
        """Generate one video, write it to output path, and return its byte length."""
